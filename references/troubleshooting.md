# Troubleshooting

Common errors encountered when using `govc` against ESXi / vCenter.

---

## Connection & Auth

### `x509: certificate signed by unknown authority`

**Cause**: ESXi/vCenter using self-signed cert (default).

**Fix**: `export GOVC_INSECURE=1` or pass `-k` flag.

For production, replace cert with one signed by your internal CA.

### `ServerFaultCode: Cannot complete login due to an incorrect user name or password`

**Cause**: Wrong credentials, or account locked.

**Checks**:
1. Test login via browser: `https://<host>/ui/`.
2. For vCenter, username must include domain: `administrator@vsphere.local`, not just `administrator`.
3. If account locked, check `/var/log/vmware/sso/` on vCenter.
4. Password in env var — check for special chars needing escape: `echo "$GOVC_PASSWORD" | od -c | head`.

### `connection refused` / `i/o timeout`

**Cause**: Network reachability or wrong port.

**Checks**:
```bash
nc -zv <host> 443
curl -k https://<host>/sdk
```

ESXi and vCenter both use 443 (HTTPS). If behind a firewall, 443 TCP must be open.

---

## VM Operations

### `The operation is not allowed in the current state of the virtual machine`

**Cause**: Operation requires a different power state.

**Fix**: most `vm.change` ops need VM powered off. Hot-add (CPU/mem) must be enabled first:
```bash
govc vm.power -off <vm>
govc vm.change -vm <vm> -mem.hotadd=true -cpu.hotadd=true
govc vm.power -on <vm>
```

### `VM ... has been deleted or is no longer available`

**Cause**: Stale inventory reference after rename, unregister, or datastore browse issue.

**Fix**: refresh inventory:
```bash
govc host.reconnect -host <host>
# Or force re-scan storage
govc host.esxcli.run -host <host> storage core adapter rescan --all
```

### `Invalid configuration for device '0'`

**Cause**: Often a disk or NIC referencing a datastore/network that no longer exists.

**Fix**: list devices, remove the broken one:
```bash
govc device.ls -vm <vm>
govc device.remove -vm <vm> <device-label>
```

### `File [...] was not found`

**Cause**: VM references a VMDK or ISO path that's missing.

**Fix**:
```bash
# List files in VM's datastore directory
govc datastore.ls -ds <ds> <vm-name>/

# Detach missing CDROM
govc device.cdrom.eject -vm <vm> cdrom-3000

# Remove missing disk
govc device.remove -vm <vm> 'disk-1000-1'
```

### `vm.destroy: VM is still powered on`

**Fix**:
```bash
govc vm.power -off <vm>   # hard power off
govc vm.destroy <vm>
```

### Guest shutdown does not complete (`vm.power -s` hangs)

**Cause**: VMware Tools not installed or stopped.

**Checks**:
```bash
govc vm.info -json <vm> | jq '.virtualMachines[0].guest.toolsStatus'
# guestToolsNotInstalled | guestToolsNotRunning | guestToolsRunning
```

Install `open-vm-tools` (Linux) or VMware Tools ISO (Windows).

---

## Snapshots

### `Cannot take snapshot while VM is vMotioning`

**Fix**: wait for vMotion to finish:
```bash
govc tasks -f | grep -i migrate
```

### Snapshot consolidation needed

**Symptom**: `vm.info` shows `consolidationNeeded: true`.

**Fix**:
```bash
govc snapshot.remove -vm <vm> -c=true '*'
```

This merges any hanging delta disks back into the base.

### Disk fills up from snapshot growth

**Cause**: Long-lived snapshot on a VM with high write churn.

**Fix**: delete the snapshot (this consolidates writes into base):
```bash
govc snapshot.tree -vm <vm>
govc snapshot.remove -vm <vm> <snap-name>
```

**Prevention**: never keep snapshots > 24h on production VMs. Use backup solution (Veeam, VDP) instead.

---

## Datastore

### `Permission to perform this operation was denied`

**Cause**: user lacks Datastore.FileManagement or Datastore.Browse privilege.

**Fix**: use admin account, or grant role:
```bash
govc role.create DatastoreOps Datastore.Browse Datastore.FileManagement
govc permissions.set -principal user@vsphere.local -role DatastoreOps /DC/datastore/ds1
```

### Upload very slow

**Cause**: govc uses HTTPS to ESXi host. Self-signed cert path may add overhead.

**Speedup options**:
- Use datastore mounted via NFS/iSCSI on a management VM, copy locally.
- Use vCenter API endpoint instead of direct host.

---

## Host

### `Host is not responding` after network change

**Fix**:
```bash
govc host.reconnect -host <host>

# If that fails, check from ESXi shell
ssh root@<host>
/etc/init.d/hostd restart
/etc/init.d/vpxa restart
```

### Can't enter maintenance mode

**Cause**: VMs can't be evacuated (no DRS, no shared storage, or no target host).

**Fix**:
1. Manually migrate VMs: `govc vm.migrate -host <other-host> <vm>`
2. Or power off VMs first.

### esxcli command not found

**Cause**: Command path is wrong. esxcli uses namespaces.

**Fix**: list valid commands:
```bash
govc host.esxcli.run -host <host> --help
govc host.esxcli.run -host <host> network --help
govc host.esxcli.run -host <host> network ip --help
```

---

## Performance / Hangs

### govc command hangs

**Checks**:
1. Add `-debug` flag to see where it's stuck.
2. `-trace` for full HTTP trace.
3. Check if vCenter is overloaded: `govc tasks -f` may show many queued tasks.

### Rate limiting

vCenter throttles API calls. Batch operations should include small sleeps or use `govc` session persistence:
```bash
export GOVC_PERSIST_SESSION=true
```

This reuses a single auth session across calls.

---

## Output Parsing Pitfalls

### Dates

govc returns ISO-8601 with timezone. Use jq:
```bash
govc events -json | jq -r '.[] | "\(.createdTime | fromdateiso8601 | strftime("%F %T"))  \(.fullFormattedMessage)"'
```

### Large numbers

Memory (bytes) and capacity (bytes) values can exceed JS safe int. jq handles them correctly if you use `tonumber`:
```bash
govc datastore.info -json | jq '.datastores[].summary.capacity | tonumber / 1073741824'
```

### Names with spaces

Always quote VM/folder/network names:
```bash
govc vm.info 'VM With Spaces'        # ✅
govc vm.info VM With Spaces          # ❌ interpreted as 3 separate args
```

Use full paths with spaces:
```bash
govc vm.info '/DC/vm/Production Folder/web-01'
```

---

## Getting More Debug Info

```bash
# Trace every HTTP call
govc -trace <command>

# Save trace to file
govc -trace <command> 2> trace.log

# Raw SOAP/XML
govc -xml <command>

# Session info
govc session.ls
```

On the ESXi side:
```bash
ssh root@<host>
tail -f /var/log/hostd.log
tail -f /var/log/vpxa.log   # if managed by vCenter
```

On vCenter:
```
/var/log/vmware/vpxd/vpxd.log
/var/log/vmware/sso/tomcat.log   # auth issues
```
