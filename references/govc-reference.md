# govc Command Reference

Comprehensive reference for `govc` commands, grouped by category. Each command supports `-h` for detailed flags.

> **Tip**: all commands accept `-json` for structured output, `-dump` for Go-struct pretty-print, and `-xml` for raw SOAP.

---

## Global Flags

```
-u URL         override GOVC_URL
-k             skip TLS verify (GOVC_INSECURE)
-debug         verbose logging
-trace         HTTP trace
-persist-session=true   cache session
-json          JSON output
-dc DC         override GOVC_DATACENTER
```

---

## Inventory & Search

| Command | Purpose |
|---|---|
| `govc ls [path]` | List inventory children (like `ls`) |
| `govc ls vm` | List all VMs |
| `govc ls host` | List all hosts |
| `govc find [-type t] [path]` | Recursive find; `-type m=vm, h=host, s=datastore, n=network, r=resourcepool, f=folder, c=cluster, d=datacenter` |
| `govc object.collect <moref>` | Dump raw managed object properties |
| `govc tree` | ASCII tree of inventory |

```bash
# All powered-on VMs
govc find -type m -runtime.powerState poweredOn

# VMs matching a name pattern
govc find -type m -name 'web-*'
```

---

## VM Operations (`vm.*`)

### Lifecycle

| Command | Purpose |
|---|---|
| `vm.create` | Create new VM (bare shell) |
| `vm.clone` | Clone existing VM or template |
| `vm.destroy` | Delete VM (must be powered off) |
| `vm.register` | Register existing .vmx into inventory |
| `vm.unregister` | Remove from inventory (keep files) |
| `vm.migrate` | vMotion to another host/datastore |
| `vm.upgrade` | Upgrade VM hardware version |

```bash
govc vm.create -m 2048 -c 2 -net 'VM Network' -g rhel9_64Guest -disk 20GB vm-name
govc vm.clone -vm template-vm -on=false new-vm
govc vm.clone -vm source -link=true -snapshot snap1 linked-clone
govc vm.migrate -host esxi2.lab -ds datastore2 vm-name   # cross-host + cross-datastore
```

### Power

| Command | Purpose |
|---|---|
| `vm.power -on <vm>` | Power on |
| `vm.power -off <vm>` | Hard power off |
| `vm.power -s <vm>` | Guest shutdown (requires VMware Tools) |
| `vm.power -r <vm>` | Reset (hard) |
| `vm.power -reboot <vm>` | Guest reboot |
| `vm.power -suspend <vm>` | Suspend |

### Info

| Command | Purpose |
|---|---|
| `vm.info -json <vm>` | Full config + runtime |
| `vm.info -e <vm>` | Include extra config |
| `vm.info -r <vm>` | Include resource usage |

### Configuration

| Command | Purpose |
|---|---|
| `vm.change -vm <vm> -m 4096 -c 4` | Change CPU/memory (must be off) |
| `vm.change -vm <vm> -e guestinfo.foo=bar` | Set guest info (for cloud-init) |
| `vm.change -vm <vm> -name new-name` | Rename |
| `vm.change -vm <vm> -annotation 'text'` | Set notes |
| `vm.change -vm <vm> -mem.hotadd=true` | Enable memory hot-add |
| `vm.change -vm <vm> -nested-hv-enabled=true` | Nested virtualization |

### Disks

| Command | Purpose |
|---|---|
| `vm.disk.create` | Add new virtual disk |
| `vm.disk.attach` | Attach existing .vmdk |
| `vm.disk.change` | Resize disk |

```bash
govc vm.disk.create -vm web-01 -name web-01/data -size 100GB -ds datastore1
govc vm.disk.change -vm web-01 -disk.label 'Hard disk 2' -size 200GB
```

### Network

| Command | Purpose |
|---|---|
| `vm.network.add` | Add NIC |
| `vm.network.change` | Change port group |
| `device.ls -vm <vm>` | List all devices |
| `device.remove -vm <vm> <device-id>` | Remove device |

### Guest ops (requires tools)

| Command | Purpose |
|---|---|
| `guest.run -vm <vm> -l user:pass cmd` | Run command inside guest |
| `guest.ls -vm <vm> -l user:pass /path` | List files inside guest |
| `guest.upload -vm <vm> -l user:pass local remote` | Copy file into guest |
| `guest.download -vm <vm> -l user:pass remote local` | Copy file out |

### IP / console

| Command | Purpose |
|---|---|
| `vm.ip <vm>` | Get VM IP (waits if not ready) |
| `vm.ip -wait 5m <vm>` | Wait up to 5 min |
| `vm.console <vm>` | Open WebMKS URL in browser |

---

## Snapshots (`snapshot.*`)

```bash
snapshot.create -vm <vm> [-m=true] [-q=true] [-d 'desc'] name
snapshot.tree   -vm <vm>             # ASCII tree with IDs
snapshot.revert -vm <vm> [name|id]
snapshot.remove -vm <vm> [name|id|* [-c=true]]   # -c consolidate
```

`-m` include memory (slow, requires VM powered on)
`-q` quiesce guest file system (requires tools)

---

## Datastore (`datastore.*`)

| Command | Purpose |
|---|---|
| `datastore.ls [-ds DS] [path]` | List files |
| `datastore.info [-ds DS]` | Capacity, type, URL |
| `datastore.upload -ds DS local remote` | Upload |
| `datastore.download -ds DS remote local` | Download |
| `datastore.mkdir -ds DS path` | Create dir |
| `datastore.rm -ds DS path` | Delete (careful!) |
| `datastore.cp -ds DS src dst` | Copy within datastore |
| `datastore.mv -ds DS src dst` | Move |
| `datastore.disk.info -ds DS path.vmdk` | VMDK metadata |
| `datastore.disk.create -ds DS -size 10G path.vmdk` | Create flat VMDK |

---

## Host (`host.*`)

```bash
host.info [-host <name>]
host.maintenance.enter -host <name>
host.maintenance.exit  -host <name>
host.reconnect         -host <name>
host.disconnect        -host <name>

# Service control (SSH, NTP, etc.)
host.service.ls     -host <name>
host.service start  -host <name> TSM-SSH
host.service stop   -host <name> TSM-SSH
host.service policy -host <name> TSM-SSH on

# Firewall
host.portgroup.info -host <name>
host.esxcli.run -host <name> network firewall ruleset list

# Hardware
host.info -k | jq '.hostSystems[0].hardware'
host.esxcli.run -host <name> hardware platform get
host.esxcli.run -host <name> storage core device list
```

---

## Network (`network.*` / `dvs.*`)

```bash
# Standard vSwitch / Port groups
host.vswitch.info    -host <name>
host.portgroup.add   -host <name> -vswitch vSwitch0 -vlan 100 PortGroupName
host.portgroup.remove -host <name> PortGroupName

# Distributed Virtual Switches (vCenter only)
dvs.create -host <host1>,<host2> DSwitch
dvs.portgroup.add -dvs DSwitch -type ephemeral PG-Name
dvs.portgroup.info -dvs DSwitch
```

---

## Events & Tasks

```bash
# Last 100 events
govc events -n 100

# Filter by entity
govc events vm/<vm-name>

# Follow live
govc events -f -n 10

# Running tasks
govc tasks -f
```

---

## OVF / OVA import/export

```bash
# Import OVF
govc import.ovf -ds datastore1 -name new-vm ./image.ovf

# Import OVA
govc import.ova -ds datastore1 -name new-vm ./image.ova

# Import with options (networks, properties)
govc import.spec -hidden ./image.ovf > spec.json
# edit spec.json
govc import.ovf -options spec.json ./image.ovf

# Export VM to OVF
govc export.ovf -vm <vm> ./out-dir
```

---

## Resource Pools (`pool.*`)

```bash
pool.create -cpu.limit=-1 -mem.limit=-1 /DC/host/Cluster/Resources/pool-a
pool.change -cpu.reservation 1000 /DC/host/Cluster/Resources/pool-a
pool.destroy /DC/host/Cluster/Resources/pool-a
```

---

## Permissions & Roles

```bash
# List roles
govc role.ls

# Create role
govc role.create Role-Name Privilege1 Privilege2

# Assign permissions
govc permissions.set -principal user@vsphere.local -role Role-Name /path

# Check who has access
govc permissions.ls /path
```

---

## Cluster (`cluster.*`)

```bash
cluster.create -host <hosts> /DC/host/Cluster
cluster.change -drs-enabled -ha-enabled /DC/host/Cluster
cluster.add -cluster /DC/host/Cluster -hostname esxi3 -username root -password pass
```

---

## Licenses

```bash
license.ls
license.add <key>
license.assign -host <host> <key>
license.remove <key>
```

---

## esxcli passthrough

`govc host.esxcli.run` invokes esxcli inside the ESXi host. Near-everything esxcli can do:

```bash
govc host.esxcli.run -host <host> network ip interface list
govc host.esxcli.run -host <host> storage nmp device list
govc host.esxcli.run -host <host> hardware cpu list
govc host.esxcli.run -host <host> system syslog config get
```

Output is always JSON-structured.

---

## Useful one-liners

```bash
# VMs using more than 50% of their allocated memory
govc find -type m | while read vm; do
  govc vm.info -json "$vm" | jq -r --arg vm "$vm" '
    .virtualMachines[0] |
    select(.summary.quickStats.guestMemoryUsage > (.config.hardware.memoryMB * 0.5)) |
    "\($vm)\t\(.summary.quickStats.guestMemoryUsage)/\(.config.hardware.memoryMB)"
  '
done

# All VMs with snapshots older than 7 days
govc find -type m | while read vm; do
  govc snapshot.tree -vm "$vm" -i -D -c 2>/dev/null | awk -v cutoff="$(date -d '7 days ago' +%s)" '
    $NF < cutoff { print vm, $0 }' vm="$vm"
done

# Power off all VMs in a folder
govc find -type m /DC/vm/Lab | xargs -I {} govc vm.power -off {}
```
