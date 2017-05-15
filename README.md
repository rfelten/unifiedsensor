## What is this? 

This is a Python 3 module to extract  _pulse signatures_ from the 2.4/5GHz ISM spectrum using the [ath9k spectral scan](https://wireless.wiki.kernel.org/en/users/drivers/ath9k/spectral_scan)
feature and a monitor interface.

This tool was written by Robert Felten for his master thesis _"Design and prototypical implementation of a Radio
Measurement Map"_.

## Example Session
 
See ```example.py```.

## Dependencies

 * iw, ifconfig, sudo
 * $ sudo apt-get install python3-setuptools
 * $USER in the sudoers file
 * ```/sys/kernel/debug``` needs to be read+writeable for the current user
 or ```$ sudo chmod -R 777 /sys/kernel/debug``` (maybe a bad idea)
 * Python modules athspectralscan and yanh
  

## Installation

```
$ sudo python3 setup.py install unifiedsensor
```


## Overview

TBA

## More Detailed Documentation (API)

  * UnifiedSensor(interface, output_queue) - Create a UnifiedSensor instance. Mandatory
  parameters are the Wi-Fi interface name (```interface```) and a queue (```output_queue```) to put the extracted signatures
  * start() - Start the sensor
  * stop() - Stop the sensor
  
## Pitfalls

 * Need run as root in order to access debugfs files. Alternatively to the user needs to allow non-root
 users to access the debugfs via ```$ sudo chmod a+rx /sys/kernel/debug```
 * Sample output is out of order. 

