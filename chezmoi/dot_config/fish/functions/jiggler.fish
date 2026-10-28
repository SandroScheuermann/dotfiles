function jiggler
    while true
        xdotool mousemove_relative 1 1
        sleep 40
        xdotool mousemove_relative -- -1 -1
    end
end
