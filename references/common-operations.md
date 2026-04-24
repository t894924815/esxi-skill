# Common Operations — Recipe Book

Playbook-style recipes for frequent ESXi / vSphere operations.

---

## 1. Daily Health Check

```bash
#!/usr/bin/env bash
# esxi-health.sh — one-shot health snapshot
set -euo pipefail

echo "=== HOSTS ==="
govc host.info -json | jq -r '
  .hostSystems[] |
  "\(.name)\t\(.runtime.connectionState)\t\(.runtime.inMaintenanceMode)\tCPU:\(.summary.quickStats.overallCpuUsage // 0)MHz/Mem:\(.summary.quickStats.overallMemoryUsage // 0)MB"
'

echo "=== DATASTORES (>80% full) ==="
govc datastore.info -json | jq -r '
  .datastores[] |
  select((.summary.capacity - .summary.freeSpace) / .summary.capacity > 0.8) |
  "\(.name)\t\((100 - .summary.freeSpace*100/.summary.capacity) | floor)% used"
'

echo "=== VMs WITH SNAPSHOTS ==="
govc find -type m | while read -r vm; do
  snap=$(govc snapshot.tree -vm "$vm" 2>/dev/null | head -1)
  [ -n "$snap" ] && echo "$vm → $snap"
done

echo "=== RECENT EVENTS ==="
govc events -n 20 | grep -Ei 'error|warn|failed' || true
```

---

## 2. Build a VM from Scratch

```bash
NAME=web-01
DS=datastore1
NET='VM Network'

# 1. Create shell
govc vm.create \
  -name "$NAME" \
  -m 4096 -c 2 \
  -g ubuntu64Guest \
  -ds "$DS" \
  -net "$NET" \
  -disk 40GB \
  -on=false

# 2. (Optional) Add second disk
govc vm.disk.create -vm "$NAME" -name "$NAME/data" -size 100GB -ds "$DS"

# 3. Mount ISO
govc device.cdrom.insert -vm "$NAME" -device cdrom-3000 "iso-repo/ubuntu-22.04.iso"
govc device.connect      -vm "$NAME" cdrom-3000

# 4. Set boot order (CD-ROM first for install)
govc vm.change -vm "$NAME" -e 'bios.bootOrder=cdrom,disk'

# 5. Power on
govc vm.power -on "$NAME"

# 6. Wait for IP
govc vm.ip -wait 10m "$NAME"
```

---

## 3. Clone from Template + Cloud-init

```bash
TEMPLATE=ubuntu-22-template
NAME=app-prod-01
HOSTNAME=app-prod-01.lab.local

# Linked clone (fast)
govc vm.clone -vm "$TEMPLATE" -on=false -link=true -snapshot base "$NAME"

# Inject cloud-init via guestinfo
USERDATA=$(base64 -w0 <<'EOF'
#cloud-config
hostname: app-prod-01
ssh_authorized_keys:
  - ssh-ed25519 AAAA... user@host
package_update: true
packages: [nginx]
EOF
)

govc vm.change -vm "$NAME" \
  -e "guestinfo.userdata=$USERDATA" \
  -e "guestinfo.userdata.encoding=base64" \
  -e "guestinfo.hostname=$HOSTNAME"

govc vm.power -on "$NAME"
govc vm.ip -wait 5m "$NAME"
```

---

## 4. Snapshot Strategy

### Safe pre-change snapshot

```bash
VM=$1
LABEL="pre-change-$(date +%Y%m%d-%H%M)"
govc snapshot.create -vm "$VM" -m=false -q=false "$LABEL"
echo "Snapshot created: $LABEL"
```

### Auto-cleanup snapshots older than N days

```bash
DAYS=7
CUTOFF=$(date -v-${DAYS}d +%s 2>/dev/null || date -d "${DAYS} days ago" +%s)

govc find -type m | while read -r vm; do
  # -D prints date, -i prints ID
  govc snapshot.tree -vm "$vm" -D -i -c 2>/dev/null | \
    awk -v cutoff="$CUTOFF" '
      {
        # Parse creation date from output — adjust based on your locale
        # Example line: "snap-1  2024-10-01 12:34  12345"
        cmd = "date -d \"" $2 " " $3 "\" +%s"
        cmd | getline ts
        close(cmd)
        if (ts < cutoff) print $1
      }' | while read -r snap; do
    echo "Removing old snapshot: $vm / $snap"
    # govc snapshot.remove -vm "$vm" "$snap"   # uncomment to actually remove
  done
done
```

### Consolidate (merge hanging snapshot disks)

```bash
govc vm.info -json "$VM" | jq '.virtualMachines[0].runtime.consolidationNeeded'
# If true:
govc snapshot.remove -vm "$VM" -c=true '*'
```

---

## 5. Migrate VMs Off a Host (for maintenance)

```bash
HOST=esxi1.lab
TARGET=esxi2.lab

# List VMs on host
VMS=$(govc find -type m -runtime.host "$HOST")

# Migrate each
for vm in $VMS; do
  echo "Migrating $vm → $TARGET"
  govc vm.migrate -host "$TARGET" "$vm"
done

# Put into maintenance mode
govc host.maintenance.enter -host "$HOST"
```

---

## 6. Bulk Create from CSV

```csv
# vms.csv
name,cpu,mem,disk,net
web-01,2,2048,40,VM Network
web-02,2,2048,40,VM Network
db-01,4,8192,200,VM Network
```

```bash
while IFS=, read -r name cpu mem disk net; do
  [ "$name" = "name" ] && continue
  echo "Creating $name..."
  govc vm.create -name "$name" -c "$cpu" -m "$mem" -g ubuntu64Guest \
    -net "$net" -disk "${disk}GB" -on=false
done < vms.csv
```

---

## 7. Tag & Organize

```bash
# List folders
govc folder.info /DC/vm

# Create folder
govc folder.create /DC/vm/Production

# Move VM into folder
govc object.mv /DC/vm/web-01 /DC/vm/Production

# Tags (vCenter only)
govc tags.category.create -m=false -t=VirtualMachine env
govc tags.create -c env prod
govc tags.create -c env staging
govc tags.attach prod /DC/vm/web-01
govc tags.ls
```

---

## 8. Network Changes

### Change VM port group

```bash
govc vm.network.change -vm web-01 -net 'DMZ-VLAN100' ethernet-0
```

### Add an NIC

```bash
govc vm.network.add -vm web-01 -net 'Backup-Net' -net.adapter vmxnet3
```

### Create port group on ESXi

```bash
# Create VLAN-tagged port group on existing vSwitch
govc host.portgroup.add -host esxi1.lab -vswitch vSwitch0 -vlan 100 'VLAN100-PG'
```

---

## 9. Datastore Cleanup

```bash
# Find orphaned files (no VM references them)
govc datastore.ls -l -ds datastore1 / | grep -v '^-' | awk '{print $4}' | while read dir; do
  # check if any VM references this directory
  if ! govc find -type m | xargs -I {} govc vm.info -json {} | \
       jq -e --arg d "$dir" '.virtualMachines[0].config.files.vmPathName | contains($d)' >/dev/null 2>&1; then
    echo "ORPHAN: $dir"
  fi
done

# Find large log files
govc datastore.ls -R -l -ds datastore1 / 2>/dev/null | awk '$2 > 100000000 {print $2, $NF}'
```

---

## 10. Upload / Download

### Upload ISO

```bash
govc datastore.mkdir -ds datastore1 iso
govc datastore.upload -ds datastore1 ./ubuntu.iso iso/ubuntu-22.04.iso
```

### Download VM disk (clone offline)

```bash
# Power off first
govc vm.power -off source-vm

# Download the VMDK + descriptor
govc datastore.download -ds datastore1 source-vm/source-vm.vmdk ./backup/source-vm.vmdk
govc datastore.download -ds datastore1 source-vm/source-vm-flat.vmdk ./backup/source-vm-flat.vmdk
```

---

## 11. Backup via OVF Export

```bash
mkdir -p /backup/$(date +%Y%m%d)
govc export.ovf -vm web-01 /backup/$(date +%Y%m%d)/web-01

# Or OVA (tarball)
govc export.ovf -vm web-01 -sha 256 -lease 30m /tmp/web-01
tar -cf /backup/web-01-$(date +%Y%m%d).ova /tmp/web-01
```

---

## 12. Query Patterns (jq)

```bash
# All VMs → name + power state
govc ls -json vm | jq -r '.elements[].Object | "\(.Name)\t\(.Runtime.PowerState)"'

# Total allocated memory across all VMs (GB)
govc ls -json vm | jq '[.elements[].Object.Summary.Config.MemorySizeMB] | add / 1024'

# Datastore free space
govc datastore.info -json | jq '.datastores[] | {name: .name, free_gb: (.summary.freeSpace/1073741824 | floor)}'

# VMs with VMware Tools not running
govc ls -json vm | jq -r '
  .elements[].Object |
  select(.Guest.ToolsRunningStatus != "guestToolsRunning") |
  .Name
'

# Hosts with DRS/HA disabled
govc ls -json host | jq -r '
  .elements[].Object |
  select(.Summary.Runtime.InMaintenanceMode == false) |
  .Name
'
```
