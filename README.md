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

The block transfer types are:
1. Energy Low Res
2. Energy High Res
3. Power Real Standard
4. Power Real Fine
5. Power Reactive Standard

To get a hex dump of the USB packets, append ```--debug```

To get human readable dates instead of Unix time, append ```--humanDate```

Even with udev rules making the device chmod 666 then sudo appears to be required just now.

## Multiple units

The units I have all have their serial number set to 0. To allow reading from multiple units,
```--unitNumber <n>``` can be appended to read from a particular unit (starting at 0).

For example, if you had 2 units attached, you could run the following to read from both units.
It appears to be stable, but moving USB ports may result in a different order.
```
sudo python reader.py --blocktransfer=4 --unitNumber 0
sudo python reader.py --blocktransfer=4 --unitNumber 1
```
## Original code

Original unpacked source from can be found in the originalSource branch. It is from [en4rab](https://www.en4rab.co.uk/onzo/).
There are also working Windows exe files at the same place. Some .zip files iare in orig as it was offline Oct 2024.

## Background

See [navitron forum page](https://www.navitron.org.uk/forum/index.php?action=printpage;topic=12168.0)
(also archived [here](https://bruce33.github.io/onzo_dumper/docs/www.navitron.org.uk-forum-topic-12168.html)) for background on this project.

