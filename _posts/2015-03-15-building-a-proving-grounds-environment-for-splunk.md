---
layout: post
title: Building a Proving Grounds Environment for Splunk Candidates
date: '2015-03-15T08:00:00-07:00'
tags:
- splunk
- environment
- terraform
- infrastructure
- training
permalink: /2015/03/building-proving-grounds-environment.html
---

# Building a Proving Grounds Environment for Splunk Candidates

I was tasked with building isolated environments for evaluating potential Splunk hires. These "proving grounds" needed to simulate real infrastructure—fast, reliable, and disposable. Each candidate got their own sandbox: a miniaturized production-like deployment with just enough complexity to prove they could navigate Splunk in the wild.

The stack for each environment looked like this:

- 1x **Linux host** (running Splunk Enterprise)  
- 1x **Windows host** (with a Universal Forwarder)  
- **Indexer Cluster** (2 nodes)  
- **Search Head**  
- **Cluster Master**  
- **Deployment Server**

There was no shared infra—each candidate got a complete environment to themselves. Yes, it’s heavy. But it’s also thorough.

---

## Infrastructure Strategy

I spun this up using Terraform, and while I hadn’t yet modularized things in a reusable way, it was a solid entry point into Infrastructure-as-Code. Here’s what mattered:

- Each stack had isolated security groups and tagging  
- Resource names were consistent, timestamped, and easy to tear down  
- AMIs were pre-baked where possible, but most of the setup happened in **user data scripts**

---

## The Important Sauce: User Data

The real magic was in the `user-data`. Below is a version of the Linux provisioning script used to configure Splunk Enterprise. It’s been scrubbed for secrets, but it’s representative of the approach and era.

```bash
#!/bin/bash

# --- STARTING USER DATA SCRIPT ---
echo "Starting Splunk setup..."

# Basic packages
yum install -y wget git

# Set hostname
hostnamectl set-hostname deploymentserver
echo "preserve_hostname: true" >> /etc/cloud/cloud.cfg
sed -i "s/^127.0.0.1 localhost/127.0.0.1 localhost deploymentserver/" /etc/hosts

# Clean any existing Splunk UF
/opt/splunkforwarder/bin/splunk stop
/opt/splunkforwarder/bin/splunk disable boot-start
rm -rf /opt/splunkforwarder

# Download Splunk Enterprise
wget -O /tmp/splunk.rpm "<REPLACE_WITH_2015_SPLUNK_RPM_URL>"
yum install -y /tmp/splunk.rpm

# Set Splunk hostname
echo "[general]" > /opt/splunk/etc/system/local/server.conf
echo "serverName = $(hostname)" >> /opt/splunk/etc/system/local/server.conf

# Set splunk.secret
mkdir -p /opt/splunk/etc/auth
cat <<EOF > /opt/splunk/etc/auth/splunk.secret
<REPLACE_WITH_SPLUNK_SECRET>
EOF
chmod 600 /opt/splunk/etc/auth/splunk.secret
chown -R splunk:splunk /opt/splunk

# Start Splunk
su - splunk -c "/opt/splunk/bin/splunk start --accept-license --no-prompt"

# Wait for Splunk to start
for i in {1..20}; do
    if su - splunk -c "/opt/splunk/bin/splunk status" | grep -q "splunkd is running"; then
        break
    fi
    sleep 5
done

# Stop and enable boot-start
su - splunk -c "/opt/splunk/bin/splunk stop"
/opt/splunk/bin/splunk enable boot-start -user splunk

# Add admin password
echo "admin:<REPLACE_WITH_HASHED_PASSWORD>" > /opt/splunk/etc/passwd
chmod 600 /opt/splunk/etc/passwd
chown splunk:splunk /opt/splunk/etc/passwd

echo "Splunk setup complete."
```

---

## Lessons Learned

- **Don’t try to test Splunk skills in a vacuum.** The only way to know if someone can handle Splunk is to watch them work inside Splunk.
- **Terraform is your friend**—even in basic form.
- **User data can be more powerful than config management** for short-lived environments.
- **Consistency makes teardown safer**—resource naming and tagging saved me multiple times.

This project kicked off a deep interest in automation and Splunk infrastructure strategy. If you're mentoring, hiring, or teaching Splunk—you need a proving grounds. And you need a repeatable way to deploy it.
