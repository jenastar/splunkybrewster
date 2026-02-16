---
layout: post
title: "UF/HF Routing to Multiple Destinations"
date: '2024-03-21T19:33:00-07:00'
permalink: /2024/03/ufhf-routing-to-multiple-destinations.html
---

## Solution

We will be using Splunk’s native TCP routing, configuration file precedence and both DS managed and unmanaged configurations to accomplish the desired result of sending to two different locations. So long as the configuration directories (aka TA’s) are uniquely named and properly placed, these configurations can coexist and provide a solution where by both teams are able to get all logs needed to each destination.

### TCP Routing

TCP Routing statements define the destination for events that are picked up by Splunk. We may define TCP Routing statements inside of inputs.conf at the individual stanza level like so:

> ## 
> 
> ``
>
>> ## 
>> 
>> `[monitor://D:\splunkylogs\Apps\*]`
>> 
>> ## 
>> 
>> `disabled = false`
>> 
>> ## 
>> 
>> `sourcetype = splunky_single_line #THIS CAN VARY`
>> 
>> ## 
>> 
>> `index = splunky-applications`
>> 
>> ## 
>> 
>> `_TCP_ROUTING = splunkcloud_1`

### TCP Routing

Another example with multiple outbound destinations:

`[monitor://D:\logs\IIS]`  
`disabled = false`  
`sourcetype = iis`  
`index = web_servers`  
`_TCP_ROUTING = splunkcloud_1, splunky-cribl`




  

Default TCP Routes must be defined in order to be called inside of the inputs.conf files. This will also be the default output destination if no other TCP_Route statement is present in the inputs.conf files. 


They may be defined inside of a custom TA (directory) like so:

`### $SPLUNK_HOME\Z_team1\default\ouputs.conf`

`[tcpout:team1]`  
`disabled = false`  
`defaultGroup = splunkcloud_1`

Or like so:

`[tcpout:splunky-cribl]`  
`disabled = false`  
`server = host.splunkynet.com:9997,host2.splunkynet.com:9997`` ``[tcpout-server://host.splunkynet.com:9997]`  
`[tcpout-server://host2.splunkynet.com:9997]`

#### Configuration File Precedence

  1. System local directory -- highest priority

  2. App local directories

  3. App default directories

  4. System default directory -- lowest priority

When consuming a global configuration, such as inputs.conf, Splunk software first uses the attributes from any copy of the file in system/local. Then it looks for any copies of the file located in the app directories, adding any attributes found in them, but ignoring attributes already discovered in system/local. As a last resort, for any attributes not explicitly assigned at either the system or app level, it assigns default values from the file in the system/default directory.  
Given this order we will have team1’s configurations live in a TA with name ‘Z_team1' and Deployment Server configurations assigned to the team1’s serverclass in a TA with name 'Y_team1'. When stanza names are unique both will be applied to the bundled configuration. 

## Bringing it Together

Given the aforementioned precedence and TCP routing basics we will arrive at a configuration that gives:  
Precedence to Splunky's default TCP route for all inputs stanzas that do not have an explicit TCP route statement defined.   
team1 the ability to define and manage their own inputs configurations so long as they’re named and placed appropriately.   
Splunky the ability to manage inputs and output definitions for all sources. 

### team1’s Action Items

  1. team1 to remove any configs from system/local  
To date, there are no files required to be removed for team1 team.  
Move team1’s custom configs as follows:**Current Directory**| **New Directory**  
---|---  
$SPLUNK_HOME\SplunkUniversalForwarder| $SPLUNK_HOME\etc\apps\Z_team1_interal_apps\local\   
$SPLUNK_HOME\100_splunky_splunkcloud| $SPLUNK_HOME\Z_team1_100_splunky_splunkcloud  

3\. Add tcp route statements to the inputs configuration file and remove inputs which will be managed by Splunky:  
`### $SPLUNK_HOME\Z_team1_interal_apps\local\inputs.conf  
``   
``[monitor://D:\splunkylogs\Apps\*]  
``disabled = false  
``sourcetype = splunky_single_line #THIS CAN VARY  
``index = splunky-applications  
``_TCP_ROUTING = splunkcloud_1  
``   
``[monitor://D:\logs\Apps\*]  
``disabled = false  
``sourcetype = splunky_single_line #THIS CAN VARY  
``index = splunky-applications  
``_TCP_ROUTING = splunkcloud_1  
`Repeat this for all custom sources.   
Ensure that these directories are not used by other teams or applications anywhere in the splunky environment  
4\. Define default output to team1 Cloud.  
`### $SPLUNK_HOME\Z_team1_100_splunky_splunkcloud\default\ouputs.conf  
``[tcpout-team1]  
``defaultGroup = splunkcloud_1`` ``###Update clientCert location   
``clientCert = $SPLUNK_HOME/etc/apps/Z_team1_100_splunky_splunkcloud/default/splunky_server.pem  
`5\. Use Octopus (use the DS or any config management) to Set Deploymentclient.conf to point to Splunky's DS  
`### $SPLUNK_HOME\system\local\deploymentclient.conf`` ``[deployment-client]  
``clientName = Cloud_Ops_$HOSTNAME  
``[target-broker:deploymentServer]  
``targetUri= https://host.splunkynet.com:8089  
`6\. Use Octopus to Set server.conf to point to new cert location  
`### server.conf  
``###Path D:\Program files\SplunkUniversalForwarder\etc\apps\Z_team1_100_splunky_splunkcloud\default  
``sslRootCAPath = $SPLUNK_HOME/etc/apps/Z_team1_100_splunky_splunkcloud/default/splunky_cacert.pem`` `

#### Splunky's Action Items for Management

  1. Define the serverclass encompassing team1’s servers

  2. Add TCP out statements to the inputs.conf

     1. `[monitor://D:\splunkylogs\IIS]  
``disabled = false  
``sourcetype = iis  
``index = web_servers  
``_TCP_ROUTING = splunkcloud_1, splunky-cribl`` ``[monitor://D:\logs\IIS]  
``disabled = false  
``sourcetype = iis  
``index = web_servers  
``_TCP_ROUTING = splunkcloud_1, splunky-cribl`` ``[WinEventLog://Application] #THESE CONFIGS WILL EXIST FOR ALL UF’s  
``disabled = 0  
``index = dev-winevt  
``_TCP_ROUTING = splunkcloud_1, splunky-cribl`

  3. Set a route from Cribl for the following:

## Validate

Logs are being received by both Splunk Cloud instances.
