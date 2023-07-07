# TdA Dynamic Deploy System

## System Deployment

### Requirements
- Ansible
- Instance to deploy to (Tested on AWS EC2 running Debian 11)
- Domain name routed to instance
- SSH key for instance (And established connection to instance)

### Steps
1. Create a hosts.ini file based on the hosts.ini.example file
2. Run following command:
`ansible-playbook --private-key={{ssh key location}} -i ansible/hosts.ini ansible/main.yaml`
3. Wait for the playbook to finish
4. Information about the routing will be visible at `traefik.{{domain name}}/dashboard`
