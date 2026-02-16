---
layout: post
title: "Splunk TCP Routing to Multiple Destinations"
date: '2024-05-22T19:37:00-07:00'
tags:
- routing
- splunk
permalink: /2024/05/splunk-tcp-routing-to-multiple.html
---

## Solution

We will be using Splunk’s native TCP routing, configuration file precedence and both DS managed and unmanaged configurations to accomplish the desired result of sending to two different locations. In this scenario there are two teams each requiring different inputs. In some cases those inputs required by Team1 are also required by Splunky's team. This scenario is a little more complex given the management by two teams. If you're just wanting routing to two destinations you should be covered by reading only the TCP Routing Basics section.  

So long as the configuration directories (aka TA’s) are uniquely named and properly placed, these configurations can coexist and provide a solution where by both teams are able to get all logs needed to each destination.

### TCP Routing Basics

TCP Routing statements define the destination for events that are picked up by Splunk. We may define TCP Routing statements inside of inputs.conf at the individual stanza level like so:



[monitor://D:\splunkylogs\Apps\\*]  
disabled = false  
sourcetype = splunky_single_line #THIS CAN VARY  
index = splunky-applications  
_TCP_ROUTING = splunkcloud_1



Another example with multiple outbound destinations:



[monitor://D:\logs\IIS]  
disabled = false  
sourcetype = iis  
index = web_servers  
_TCP_ROUTING = splunkcloud_1, splunky-cribl 





Default TCP Routes must be defined in order to be called inside of the inputs.conf files. This will also be the default output destination if no other TCP_Route statement is present in the inputs.conf files.


They may be defined inside of a custom TA (directory) like so:


  

> ### $SPLUNK_HOME\Z_team1\default\ouputs.conf



> [tcpout:team1]  
> disabled = false  
> defaultGroup = splunkcloud_1


  

Or like so:


  


> [tcpout:splunky-cribl]
> 
> disabled = false
> 
> server = host.splunkynet.com:9997,host2.splunkynet.com:9997 



> [tcpout-server://host.splunkynet.com:9997]
> 
> [tcpout-server://host2.splunkynet.com:9997]

### Configuration File Precedence

>   * System local directory -- highest priority
>   * App local directories
>   * App default directories
>   * System default directory -- lowest priority
> 


From the docs, "When consuming a global configuration, such as inputs.conf, Splunk software first uses the attributes from any copy of the file in system/local. Then it looks for any copies of the file located in the app directories, adding any attributes found in them, but ignoring attributes already discovered in system/local. As a last resort, for any attributes not explicitly assigned at either the system or app level, it assigns default values from the file in the system/default directory."  

  
Given this order we will have team1’s configurations live in a TA with name ‘Z_team1' and Deployment Server configurations assigned to the team1’s serverclass in a TA with name 'Y_team1'. When stanza names are unique both will be applied to the bundled configuration.

### Bringing it Together

Given the aforementioned precedence and TCP routing basics we will arrive at a configuration that gives:  

>   * Precedence to Splunky's default TCP route for all inputs stanzas that do not have an explicit TCP route statement defined.
>   * Team1 the ability to define and manage their own inputs configurations so long as they’re named and placed appropriately (TA/Dir prefix Z).
>   * Splunky the ability to (DS) manage inputs and output definitions for all sources.
> 



### Team1’s Action Items

This is for the case of managing the servers with the DS but also having a team wanting to leverage their own input configurations eperately from the DS. 

#### Team1 to remove any configs from system/local



#### Move Team1’s custom configs as follows:

Current Directory

1\. $SPLUNK_HOME\SplunkUniversalForwarder (they were using this for input definitions)   
2\. $SPLUNK_HOME\100_splunkcloud (this was their default Splunk cloud auth app)


New Directory  
1\. $SPLUNK_HOME\etc\apps\Z_team1_interal_apps\local\  
2\. $SPLUNK_HOME\Z_team1_100_splunkcloud 



Note that we have two destinations and so the need for two Slunk Cloud auth apps. Team1 will be subordinate hence the "Z"  


#### Add tcp route statements to the inputs configuration file and remove inputs which will be managed by Splunky:



> ### $SPLUNK_HOME\Z_team1_interal_apps\local\inputs.conf
> 
>   
> 
> 
> [monitor://D:\Team1\Apps\\*]
> 
> disabled = false
> 
> sourcetype = json #THIS CAN VARY
> 
> index = Team1-applications
> 
> _TCP_ROUTING = splunkcloud_1



> [monitor://D:\logs\Apps\\*]
> 
> disabled = false
> 
> sourcetype = splunky_single_line #THIS CAN VARY
> 
> index = splunky-applications
> 
> _TCP_ROUTING = splunkcloud_1

Repeat this for all custom sources.   
Ensure that these directories are not used by other teams or applications anywhere in the splunky environment.



#### Define default output to team1 Cloud.

This is so that Team1's inputs will go to their cloud instance if we have not written an output statement for them that would override this. 





> ### $SPLUNK_HOME\Z_team1_100_splunky_splunkcloud\default\ouputs.conf
> 
> [tcpout-team1]
> 
> defaultGroup = splunkcloud_1 ###Update clientCert location 
> 
> clientCert = $SPLUNK_HOME/etc/apps/Z_team1_100_splunky_splunkcloud/default/splunky_server.pem

#### Use Octopus (use the DS or any config management) to Set Deploymentclient.conf to point to Splunky's DS



> ### $SPLUNK_HOME\system\local\deploymentclient.conf [deployment-client]
> 
> clientName = Cloud_Ops_$HOSTNAME
> 
> [target-broker:deploymentServer]
> 
> targetUri= https://host.splunkynet.com:8089

#### Use Octopus to Set server.conf to point to new cert location



> ### server.conf  
> ###Path D:\Program files\SplunkUniversalForwarder\etc\apps\Z_team1_100_splunky_splunkcloud\default  
> sslRootCAPath = $SPLUNK_HOME/etc/apps/Z_team1_100_splunky_splunkcloud/default/splunky_cacert.pem

### Splunky's Action Items

#### Define the serverclass encompassing Team1’s servers

Make sure Team1's servers are in a class of their own where they will not get conflicting configurations (deny list them from the windows/Linux default groups, duh!). Assign the TAs that begin with 



#### Add TCP out statements to the inputs.conf





> [monitor://D:\splunkylogs\IIS]  
> disabled = false  
> sourcetype = iis  
> index = web_servers  
> _TCP_ROUTING = splunkcloud_1, splunky-cribl 



> [monitor://D:\logs\IIS]  
> disabled = false  
> sourcetype = iis  
> index = web_servers  
> _TCP_ROUTING = splunkcloud_1, splunky-cribl 



> [WinEventLog://Application] #THESE CONFIGS WILL EXIST FOR ALL UF’s  
> disabled = 0  
> index = dev-winevt  
> _TCP_ROUTING = splunkcloud_1, splunky-cribl



####  Validate. Kick back.
