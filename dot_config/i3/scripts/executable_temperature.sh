#!/bin/sh

for path in \
    /sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon*/temp1_input \
    /sys/devices/platform/coretemp.0/hwmon/hwmon*/temp1_input \
    /sys/class/thermal/thermal_zone0/temp; do
    for input in $path; do
        if [ -r "$input" ]; then
            value=$(awk '{ printf "%.0f", $1 / 1000 }' "$input")
            printf '%s°C\n' "$value"
            exit 0
        fi
    done
done

printf -- '--°C\n'
