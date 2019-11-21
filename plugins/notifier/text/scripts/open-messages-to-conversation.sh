#!/bin/sh

osascript <<END
    set rowNum to $1 as integer
	--log rowNum

	tell application "Messages"
		activate
		delay 1

		tell application "System Events"
			-- log (get properties of row 3 of table 1 of scroll area 1 of splitter group 1 of window 1 of application process "Messages")
			set selected of row rowNum of table 1 of scroll area 1 of splitter group 1 of window 1 of application process "Messages" to true
		end tell
	end tell
END