# Ansible inventory for the lab fleet

`group_vars/<group>.json` is the desired-state document for that group. It is the same JSON the agent already accepts. Ansible reads `.json` group_vars, so this tree is a normal inventory.

`inventory/hosts.ini` lists device ids (`ANDROID_ID`) under a group. One device, one group.

Apply it to the lab sqlite store:

```bash
python3 server/ansible_sync.py \
  --db server/fleet.sqlite \
  --inventory ansible/inventory/hosts.ini \
  --group-vars ansible/group_vars
```

The check-in server must be started with that same `--db`. A device override set with `fleet_store.py set-desired` still wins over the group.
