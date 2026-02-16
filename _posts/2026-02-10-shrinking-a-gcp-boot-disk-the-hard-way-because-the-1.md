---
layout: post
title: Shrinking a GCP Boot Disk the Hard Way (Because There Is No Easy Way)
date: '2026-02-10T09:00:00-07:00'
tags:
- gcp
- backend
- architecture
- splunk
permalink: /2026/02/shrinking-gcp-boot-disk-hard-way_0101192637.html
---

You can't shrink a persistent disk in GCP. You can grow one in about 3 seconds, but shrinking? Google basically says "lol no." So when I needed to take a 10TB boot disk down to 2.5TB on a production Splunk server, I had to get creative.

Here's what I did, what went wrong, and what I'd do differently.

## The Setup

Production Splunk instance running on a 10TB pd-ssd boot disk in GCP. After migrating to SmartStore (which moves warm/cold buckets to GCS), actual disk usage dropped to about 2TB. Paying for 10TB of SSD when you're using 2TB is not a great look.

## The Plan

1. Snapshot the existing disk for safety
2. Create a new 2.5TB pd-ssd, attach it to the running VM as a secondary disk
3. Replicate the partition layout, format it
4. rsync everything over while Splunk is still running (no downtime yet)
5. Stop Splunk, do a final rsync to catch any changes
6. Install GRUB on the new disk
7. Stop the VM, swap the boot disk, start it up

Simple enough, right?

## Step 1: Snapshot + Create New Disk

Take a snapshot first because you're not an animal:

```bash
gcloud compute snapshots create my-instance-pre-shrink \
    --source-disk=my-instance --source-disk-zone=us-central1-a \
    --project=my-project-id
```

Create the new smaller disk and attach it to the running VM:

```bash
gcloud compute disks create my-instance-v2 \
    --project=my-project-id --zone=us-central1-a \
    --size=2500GB --type=pd-ssd

gcloud compute instances attach-disk my-instance \
    --disk=my-instance-v2 --zone=us-central1-a \
    --project=my-project-id
```

## Step 2: Partition + Format (on the server)

SSH in and set up the new disk. First attempt was `sgdisk /dev/sda -R /dev/sdb` to clone the partition table, but partition 1 on the old disk was 9.8TB - doesn't fit on a 2.5TB disk. Had to manually recreate the layout matching the boot partitions and letting the root partition fill the rest:

```bash
sgdisk -Z /dev/sdb
sgdisk -n 14:2048:10239 -t 14:EF02 \
       -n 15:10240:227327 -t 15:EF00 \
       -n 1:227328:0 -t 1:8300 /dev/sdb

mkfs.ext4 -m 0 /dev/sdb1
```

Pro tip: add `-L cloudimg-rootfs` to the mkfs command if your fstab uses labels. I didn't, and it bit me later.

## Step 3: Copy Everything with rsync

Copy boot partitions first (tiny, instant):

```bash
dd if=/dev/sda14 of=/dev/sdb14 bs=1M
dd if=/dev/sda15 of=/dev/sdb15 bs=1M
```

Mount and bulk rsync while Splunk is still running - no downtime yet:

```bash
mkdir /mnt/newdisk
mount /dev/sdb1 /mnt/newdisk
screen -S rsync
rsync -axHAX --progress / /mnt/newdisk/ --exclude=/mnt/newdisk
```

Use screen. I didn't the first time and got lucky the SSH session held for 90 minutes. Don't be me.

## Step 4: Stop Splunk + Final rsync

```bash
/opt/splunk/bin/splunk stop
rsync -axHAX --delete --progress / /mnt/newdisk/ --exclude=/mnt/newdisk
```

## Step 5: Install GRUB

```bash
mount --bind /dev /mnt/newdisk/dev
mount --bind /proc /mnt/newdisk/proc
mount --bind /sys /mnt/newdisk/sys
mount --bind /run /mnt/newdisk/run

chroot /mnt/newdisk
mount /dev/sdb15 /boot/efi
grub-install /dev/sdb
update-grub
exit

umount /mnt/newdisk/{dev,proc,sys,run}
umount /mnt/newdisk
```

Don't forget to mount the EFI partition inside the chroot. `grub-install` will fail with "cannot find EFI directory" without it.

## Step 6: Swap the Boot Disk

From your local CLI (not the server):

```bash
gcloud compute instances stop my-instance \
    --zone=us-central1-a --project=my-project-id

gcloud compute instances detach-disk my-instance \
    --disk=my-instance --zone=us-central1-a \
    --project=my-project-id

gcloud compute instances detach-disk my-instance \
    --disk=my-instance-v2 --zone=us-central1-a \
    --project=my-project-id

gcloud compute instances attach-disk my-instance \
    --disk=my-instance-v2 --boot \
    --zone=us-central1-a --project=my-project-id

gcloud compute instances start my-instance \
    --zone=us-central1-a --project=my-project-id
```

## What Actually Went Wrong

### UEFI compatibility error on boot disk attach

This was the fun one. The `attach-disk --boot` command failed with: "UEFI setting must be the same for the instance and the boot disk."

The original disk had guest OS features like `UEFI_COMPATIBLE`, `VIRTIO_SCSI_MULTIQUEUE`, `SEV_CAPABLE`, `GVNIC` baked in. The new disk we created from scratch didn't have any of these.

Check what features your existing disk has:

```bash
gcloud compute disks describe my-instance \
    --zone=us-central1-a --project=my-project-id \
    --format="yaml(guestOsFeatures)"
```

The fix: create an image from the new disk with the correct guest OS features, delete the old disk, and recreate it from the image:

```bash
gcloud compute images create my-instance-v2-img \
    --source-disk=my-instance-v2 \
    --source-disk-zone=us-central1-a \
    --guest-os-features=UEFI_COMPATIBLE,VIRTIO_SCSI_MULTIQUEUE,SEV_CAPABLE,GVNIC \
    --project=my-project-id

gcloud compute disks delete my-instance-v2 \
    --zone=us-central1-a --project=my-project-id

gcloud compute disks create my-instance-v2 \
    --image=my-instance-v2-img \
    --zone=us-central1-a --type=pd-ssd --size=2500GB \
    --project=my-project-id
```

One gotcha: `SECURE_BOOT` shows up in the disk description but it's not a valid value for `--guest-os-features`. Check valid values first instead of copying everything blindly.

Then retry the attach-disk --boot and start commands from Step 6.

### PARTUUID mismatch after image recreation

This one kept production down longer than I wanted. The VM booted to an initramfs shell with: `ALERT! PARTUUID=2ea6b9e7-... does not exist.`

When GCP created a new disk from the image, it assigned new PARTUUIDs. But GRUB's config still referenced the PARTUUIDs from before the image step. On GCP Ubuntu instances, the PARTUUID is hardcoded in `/etc/default/grub.d/40-force-partuuid.cfg`.

The fix: boot from the old disk, mount the new disk, and update the PARTUUID.

```bash
# Stop the VM, swap old disk back as boot, attach new as secondary
gcloud compute instances stop my-instance \
    --zone=us-central1-a --project=my-project-id

gcloud compute instances detach-disk my-instance \
    --disk=my-instance-v2 --zone=us-central1-a \
    --project=my-project-id

gcloud compute instances attach-disk my-instance \
    --disk=my-instance --boot \
    --zone=us-central1-a --project=my-project-id

gcloud compute instances attach-disk my-instance \
    --disk=my-instance-v2 \
    --zone=us-central1-a --project=my-project-id

gcloud compute instances start my-instance \
    --zone=us-central1-a --project=my-project-id
```

SSH in, then find and fix the PARTUUID:

```bash
# Get the actual PARTUUID of the new disk
blkid /dev/sdb1

# Mount the new disk
mkdir -p /mnt/newdisk && mount /dev/sdb1 /mnt/newdisk

# Replace the old PARTUUID with the new one
sed -i 's/OLD_PARTUUID/NEW_PARTUUID/g' \
    /mnt/newdisk/etc/default/grub.d/40-force-partuuid.cfg

# Chroot and regenerate GRUB
mount --bind /dev /mnt/newdisk/dev
mount --bind /proc /mnt/newdisk/proc
mount --bind /sys /mnt/newdisk/sys
mount --bind /run /mnt/newdisk/run
chroot /mnt/newdisk
update-grub
exit
umount /mnt/newdisk/{dev,proc,sys,run}
umount /mnt/newdisk
```

Then stop the VM, swap the disks again (Step 6), and try booting from the new disk.

### Filesystem label missing

Even after fixing the PARTUUID, the root partition mounted read-only. `/etc/fstab` referenced `LABEL=cloudimg-rootfs` and the new disk's partition had no label. Quick fix once you're booted:

```bash
e2label /dev/sda1 cloudimg-rootfs
mount -o remount,rw /
```

Or avoid this entirely by setting the label during mkfs: `mkfs.ext4 -L cloudimg-rootfs -m 0 /dev/sdb1`

## What I'd Do Differently

1. **Check guest OS features on the source disk first.** Before trying to attach anything as a boot disk, compare the features. Would have saved the whole image creation detour.

2. **Always use screen/tmux for long-running operations.** Especially on production.

3. **After creating an image and recreating a disk, always update PARTUUIDs.** The image process changes them. This is the one that really got me.

4. **Set the filesystem label during mkfs.** `mkfs.ext4 -L cloudimg-rootfs /dev/sdb1` would have avoided the read-only mount issue entirely.

5. **Don't try to sgdisk -R when the source disk is bigger.** Just create the partitions manually from the start.

## The Result

10TB pd-ssd down to 2.5TB pd-ssd. Splunk came back up, SmartStore reconnected, Tailscale picked right up. Some brief ingestion latency while Splunk caught up from the downtime, but everything settled within the hour.

Total savings: about $1,100/month in GCP persistent disk costs.

Not bad for an afternoon of sweating over a production server.
