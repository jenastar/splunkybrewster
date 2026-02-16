---
layout: post
title: Populating Splunk Asset Lookups with TA-LDAPSearch
date: '2017-02-16T08:30:00-07:00'
tags:
- splunk
- ldap
- enterprise-security
- infrastructure
permalink: /2017/02/populating-splunk-asset-lookups-with-ta.html
---

Splunk Enterprise Security depends heavily on accurate asset and identity data. In environments where Active Directory is the system of record, using the Splunk-supported **TA-ldapsearch** is the most direct way to populate `assets.csv` lookups with real-time directory data. Here's how we do it.

## Configure `ldap.conf`

First, configure your LDAP connection in `$SPLUNK_HOME/etc/apps/SA-ldapsearch/local/ldap.conf`:

```ini
[default]
host = dc01.example.com
port = 389
binddn = CN=SplunkLDAPUser,OU=ServiceAccounts,DC=example,DC=com
binddnpassword = MySuperSecretPassword
ssl = 0
userBaseDN = OU=Users,DC=example,DC=com
groupBaseDN = OU=Groups,DC=example,DC=com
userNameAttribute = sAMAccountName
realNameAttribute = displayName
disabledAttribute = userAccountControl
disabledValue = 514
objectClass = user
```

Then restart Splunk or run `| reload ldap` to pick up the new config.

## Writing the LDAP Search

Use the `ldapsearch` SPL command to pull asset attributes. A simple example:

```spl
| ldapsearch domain=default search="(&(objectClass=computer)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))" attrs="cn,dnsHostName,operatingSystem,whenCreated,managedBy"
| eval ip=""
| rename cn as asset, dnsHostName as nt_host, operatingSystem as os
| table ip, nt_host, asset, os
```

This returns all computer objects that aren't disabled, renames fields for ES compatibility, and leaves `ip` empty (unless you have it in AD).

## Schedule and Output to Lookup

Save the above as a saved search, then configure it to **output to the `assets.csv` lookup**:

```spl
| ldapsearch domain=default search="(&(objectClass=computer)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))" attrs="cn,dnsHostName,operatingSystem"
| rename cn as asset, dnsHostName as nt_host, operatingSystem as os
| eval ip=""
| table ip, nt_host, asset, os
| outputlookup append=false assets.csv
```

Set this search to run every 12 hours. Make sure it's scheduled with an account that has access to the TA-ldapsearch app context.

## Field Format Requirements

Splunk ES expects the following fields in `assets.csv`:

* `ip` (optional)
* `nt_host` (FQDN or hostname)
* `asset` (human-readable label)
* `os` (optional)
* `mac` (optional)
* `priority` (optional)

Missing `ip` is fine—ES will use DNS or other data models to resolve names.

## Testing and Troubleshooting

* Use `| ldaptestconnection` to validate the bind credentials and connectivity.
* Confirm returned fields match the ES CIM by inspecting `| inputlookup assets.csv | head 5`
* If data isn't showing up in Asset Investigator, check that the lookup is global and permissions are correct.

## Wrap-up

By leveraging the TA-ldapsearch, we eliminate the need for brittle scripts or third-party imports. With scheduled searches enriching `assets.csv`, Splunk ES gets accurate, real-time context from AD with minimal overhead.
