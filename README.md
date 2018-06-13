# onzo_dumper

## Linux Onzo Smart Energy Monitor

This project reads data from the Onzo Smart Meter (USB VID/PID 04d8:003f) by taking code from
the original wrapped-python, Windows exe.

It has only been briefly tested

1. Only tested on Ubuntu Linux 18.06 x64
2. udev rules will be required
3. requires pyusb ```pip install pyusb```

![Onzo](https://github.com/bruce33/onzo_dumper/blob/master/docs/Onzo.jpg)

## Running

```
sudo python reader.py --blocktransfer=1
sudo python reader.py --blocktransfer=2
sudo python reader.py --blocktransfer=3
sudo python reader.py --blocktransfer=4
sudo python reader.py --blocktransfer=5
```

For each blocktransfer type, a file will be produced. An example of running with blocktransfer 3 and 4 (with different date
formats, see below) are in the [docs](https://github.com/bruce33/onzo_dumper/tree/master/docs) directory.

To get a hex dump of the USB packets, append ```--debug```

To get human readable dates instead of Unix time, append ```--humanDate```

Even with udev rules making the device chmod 666 then sudo appears to be required just now.

## Original code

Original unpacked source from can be found in the originalSource branch. It is from [en4rab](https://www.en4rab.co.uk/onzo/).
There are also working Windows exe files at the same place. 

## Background

See [navitron forum page](https://www.navitron.org.uk/forum/index.php?action=printpage;topic=12168.0)
(also archived [here](https://bruce33.github.io/onzo_dumper/docs/www.navitron.org.uk-forum-topic-12168.html)) for background on this project.

