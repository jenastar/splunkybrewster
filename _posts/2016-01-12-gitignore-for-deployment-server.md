---
layout: post
title: Gitignore for Deployment Server
date: '2016-01-12T08:00:00-07:00'
tags:
- splunk
- environment
- git
- configmanagement
permalink: /2016/01/gitignore-for-deployment-server.html
---

# Managing Splunk Deployment Server Apps with Git

There are a few clean ways to manage your deployment server's apps using Git. I chose a setup that keeps the repo directly inside the `$SPLUNK_HOME/etc` directory so the full `deployment-apps/` structure is version-controlled.

This let me back up and manage every custom TA delivered to forwarders—without dumping Splunk system files or app-specific local state into the repo.

## Git Placement

Here’s how I set it up:

```bash
cd $SPLUNK_HOME/etc
git init
git remote add origin git@github.com:your-org/splunk-deployment-apps.git
```

At this point, I only wanted to track `deployment-apps/`, `system/local/serverclass.conf`, and a couple of documentation files. Everything else—especially anything sensitive or dynamic—needed to be ignored.

## .gitignore Strategy

This `.gitignore` keeps the repo clean and focused on exactly what should be under version control:

```gitignore
# Ignore everything
*
# But not these files...
!.gitignore
!README.md
# ...and not these directories...
!deployment-apps/
!deployment-apps/*/
!deployment-apps/*/*/
!deployment-apps/*/*/*/
!deployment-apps/*/*/*/*/
# ...and not these specific files
!deployment-apps/**
!system/
!system/local/
!system/local/serverclass.conf
# But still ignore some things in deployment-apps
deployment-apps/**/*.log
deployment-apps/**/*.tmp
deployment-apps/**/local/
deployment-apps/**/lookups/
deployment-apps/**/metadata/local.meta
# Ignore any potential secrets or sensitive files
**/*password*
**/*secret*
**/*.pem
**/*.key
# Ignore OS generated files
.DS_Store
Thumbs.db
```

## Commit Process

Once `.gitignore` was dialed in, it became safe to do full-app drops or updates via `git pull` or `git push`. Here’s a typical pattern I followed after staging changes:

```bash
git add .
git commit -m "Update custom TA for cloud auth"
git push origin main
```

This made my deployment server state portable and backed up in version control. It also meant other engineers could replicate or review changes to Splunk delivery logic in the same way they would code.

## Why This Matters

Deployment servers can quietly turn into config sprawl—especially when multiple TAs evolve over time. Tracking changes in Git lets you diff versions, roll back mistakes, and even trigger CI/CD validation or tests for your apps before they hit production.
