---
layout: post
title: Shrinking a GCP Boot Disk the Hard Way (Because There Is No Easy Way)
date: '2026-02-10T09:00:00-07:00'
tags:
- gcp
- backend
- architecture
- splunk
permalink: /2026/02/shrinking-gcp-boot-disk-hard-way.html
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

## What Actually Happened

### Partition table copy failed

`sgdisk /dev/sda -R /dev/sdb` tries to clone the partition table exactly. But partition 1 on the old disk was 9.8TB - which obviously doesn't fit on a 2.5TB disk. Had to manually recreate the partition layout matching the boot partitions (EFI and BIOS boot) and letting the root partition fill the rest:

```bash
sgdisk -Z /dev/sdb
sgdisk -n 14:2048:10239 -t 14:EF02 \
       -n 15:10240:227327 -t 15:EF00 \
       -n 1:227328:0 -t 1:8300 /dev/sdb
```

### Forgot to use screen

Started the initial rsync over SSH without screen. If that SSH session dropped, the rsync would have died. Got lucky - it ran for about 90 minutes without issues. Used screen for the subsequent rsyncs though.

### GRUB couldn't find EFI directory

Running `grub-install /dev/sdb` inside the chroot failed because the EFI partition wasn't mounted. Had to mount it first:

```bash
mount /dev/sdb15 /boot/efi
grub-install /dev/sdb
```

### UEFI compatibility error on boot disk attach

This was the fun one. After all the rsync and GRUB work, I tried to attach the new disk as boot:

```bash
gcloud compute instances attach-disk splunk-master \
    --disk=splunk-master-v2 --boot ...
```

GCP said no: "UEFI setting must be the same for the instance and the boot disk." The original disk had guest OS features like `UEFI_COMPATIBLE`, `VIRTIO_SCSI_MULTIQUEUE`, `SEV_CAPABLE`, `GVNIC` baked in. The new disk didn't.

The fix: create an image from the new disk with the correct guest OS features, then create a new disk from that image.

```bash
gcloud compute images create splunk-master-v2-img \
    --source-disk=splunk-master-v2 \
    --source-disk-zone=us-central1-a \
    --guest-os-features=UEFI_COMPATIBLE,VIRTIO_SCSI_MULTIQUEUE,SEV_CAPABLE,GVNIC \
    --project=security-operations-311219
```

One more gotcha here: I initially included `SECURE_BOOT` in the features list because it showed up in the old disk's description. It's not a valid value for `--guest-os-features`. Check valid values before guessing.

### PARTUUID mismatch after image recreation

This one kept production down longer than I wanted. After creating the image and recreating the disk from it, GCP assigned new PARTUUIDs to the disk. But GRUB's config still referenced the old PARTUUIDs from before the image step.

Boot dropped to an initramfs shell with: `ALERT! PARTUUID=2ea6b9e7-... does not exist.`

The fix:
1. Stop the VM
2. Reattach the old 10TB disk as boot, new disk as secondary
3. Boot from old disk, mount new disk
4. Find the actual PARTUUID: `blkid /dev/sdb1`
5. Update `/etc/default/grub.d/40-force-partuuid.cfg` with the correct PARTUUID
6. Chroot into the new disk, run `update-grub`
7. Swap disks again

### Filesystem label missing

Even after fixing the PARTUUID, the root partition mounted read-only because `/etc/fstab` referenced `LABEL=cloudimg-rootfs` and the new disk's partition had no label. Quick fix:

```bash
e2label /dev/sda1 cloudimg-rootfs
mount -o remount,rw /
```

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
