#!/usr/bin/env /Users/wrenjr/.nvm/versions/node/v11.12.0/bin/node
/* jshint esversion: 8 */
/* jshint asi: true */


// <bitbar.title>Slack Team Notifications</bitbar.title>
// <bitbar.version>v1.0.0</bitbar.version>
// <bitbar.author>Benji Encalada Mora</bitbar.author>
// <bitbar.author.github>benjifs</bitbar.author.github>
// <bitbar.image>https://i.imgur.com/x1SoIto.jpg</bitbar.image>
// <bitbar.desc>Show notifications for Slack teams and channels with option to mark as read.</bitbar.desc>
// <bitbar.dependencies>node.js superagent</bitbar.dependencies>

const request = require('superagent');
//const fs = require('fs');
const path = require('path');
const tokens = require('./resources/slack-notifier/token.js');

//var tokens = fs.readFileSync(path.join(__dirname, "../resources/tokens.txt"), "utf-8").split("\n");

// Set DARK_MODE = true to force white icon
const DARK_MODE = process.env.BitBarDarkMode;

const DEBUG = process.argv.indexOf('--debug') > 0;
const SCRIPT = process.argv[1];

// Slack API
const SLACK_API = 'https://slack.com/api/';
const SLACK_CHANNELS = 'channels';
const SLACK_GROUPS = 'groups';
const SLACK_CONVERSATIONS = 'conversations';
const SLACK_IM = 'im';
const SLACK_TEAM = 'team';
const SLACK_USERS = 'users';
const SLACK_USER_CONVERSATIONS = 'users.conversations';
const SLACK_INFO = '.info';
const SLACK_MARK = '.mark';
const SLACK_PREFS = '.prefs.get';

// ICONS {
// Original Slack icon (unused)
const SLACK_ICON = 'image=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';

// Dark Slack Icon
const SLACK_ICON_B = 'image=iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAAAXNSR0IArs4c6QAAAAlwSFlzAAAWJQAAFiUBSVIk8AAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAABLNJREFUWAmllstvTVEUxg9Vr1BVYYBIDJpIGGAibdN2RoIwYCBG5R/pjZAwYoSJQRO0BgYMqKQdVycqIpHcDkx1QpXE+/H9ztnftXvt++yXfGevs/baa6+91jr73ixrjFWRyajksvhOnBIHRLBa7MilLOvXyBw22JZEI/ZlXcujnYxr5Z8EhyOPQ4l51kwEG/uKlrQm+tTHtAzH38Wf4m/xi4huVjSQ0TGHDbasQYcPsKYY0k9SXQ8+EWUwCBL9uqDYp7E7EBkwh40PhO4ID8E+i7eqZ91oI9vPQeak1Yj7J3VAB+Ax5aPiM+WgMimBtINHIo7Wii7bj6D7FUYNK0czAZH2snghbEdQZJaRU28RXRpnQar2EJcMGYeplLL5mPhKPCf2iDQs9jTwJ7FLTK2VOgkO4YSwDn/5SX2qXIGyDuY0B1PYJqVLnJqPdQRDqaGRx0FWfKqjkvvEzqBzoHqtgBNBgiewh6KBn9Qaz3tkPX3YK54WN4kz4jOxgnFJOGyVk1qzMXjZrfFj8EGm7MvNPxrsGEZEz3v05ZmVwiQLiZyxGX4L625rBHvEegFdyq2y7JBGB4EP74uuJGbzIi+UwYbNjLZf0DrKvENcCj5SGbqsOXBNxP/XMCITFGOZevJ1AORWYPv1WkQf2GktH2wI+EKBr4pY7sLpazSCS8DCevTpsQdvxQ+ByIDS44OvCHvwshgqX5b9YGdfeSz9UqBslyfCRgzHa/h5GtnQc+wVB+S9iSXHoJ7PRZqSSw7y+8WILiZ9wjsndjBk2iUkKK4EbOivW+IG0bgugQDIqv2z95CY3xu+pHjnV7u6tr6XvCnNSL/gEKB3WWKZXmFDbGPQc5tFysm9xbgogo74YixUxZMTEBjZIIAYBEgTNwI+tor8FSFgSAB8nTB1ibImB+lyySgVp2fyhmiQ9psiZXDJToZJZ49Xykg5OUyKboe4JWZlOyzmGNCTzWNyGt5pQIPGjG0sOyjsCMb6dkZiyaaDE361nVpfAQ7oTLBBT7qxw55NyYYxJwEdZcaG/jDj92rZvqboof0i8N9OZNfXDX4YpUBprMMe7BW7ReaQgf8r2U+h/eeX93jOvg7ghJoCojYsvw8KAq8GmQA4JgD8+ILzeqmagu2XCOhuWIKScnDLOuKJaC6IlcEnJDDs+bz9d4Qy+WtqNLLOAd2TnOO+njiOOZLPFI8rYY7FtmFTZL6kXSLgS3wi2qaVcRwHLsV5yWNin8jn+Fgsi5SCjDWCT0hzclOfFQ+KZJE5gq8Fguazn7QBi5x+6xhpXgecyhAbOUM7WbBC5HGwIU4BATgwn8oB5QZVD9b5MPQJPwlXw6gh98dH8UB8IZJtZ1LiMuCrXhYrxg4olSH3ECXuEbeLOE7xovTAV0bxlnjylTUDNqkF5sgUAS6KvNN3ZM3XwB3JvSI2dYNqNiCXUv5qAhsyytgZZK4DfxSnJIO6vlySwrT2k88dxJmyY/cb86kesZ3/Ifgd+//QKEMOYCZa6d5xOd5ojlJBZMAca7F1APZhn5pqD3aYujxxPhS5HZSMrpr5pSe9fUVLWhdjJ6NaPi8uiNPigAjItJu1XzJz2GBbEo3Yl3XLxr+Yk+18ezbHlQAAAABJRU5ErkJggg==';

// White Slack Icon
const SLACK_ICON_W = 'image=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'

// Unread Slack Icon
const SLACK_ICON_UNREAD = 'image=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bG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiCiAgICB4bWxuczpwbHVzPSJodHRwOi8vbnMudXNlcGx1cy5vcmcvbGRmL3htcC8xLjAvIgogICAgeG1sbnM6R0lNUD0iaHR0cDovL3d3dy5naW1wLm9yZy94bXAvIgogICAgeG1sbnM6ZGM9Imh0dHA6Ly9wdXJsLm9yZy9kYy9lbGVtZW50cy8xLjEvIgogICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iCiAgICB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iCiAgIHhtcE1NOkRvY3VtZW50SUQ9ImdpbXA6ZG9jaWQ6Z2ltcDowMzdiYzBiOC1hYjhlLTRiNjgtOWU0Yy1mMjIyZDk4Y2ZiMzIiCiAgIHhtcE1NOkluc3RhbmNlSUQ9InhtcC5paWQ6ODI0OGJmY2YtNDY3Mi00OGRhLWE2MDAtNTU5OTJmMWUyM2EwIgogICB4bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ9InhtcC5kaWQ6ODJjZDkzZDMtZWYyNy00NTk5LWE1MTktN2M1Yjc0ODZlYjlhIgogICBHSU1QOkFQST0iMi4wIgogICBHSU1QOlBsYXRmb3JtPSJNYWMgT1MiCiAgIEdJTVA6VGltZVN0YW1wPSIxNTU4NzI5ODQ1ODM0NzYwIgogICBHSU1QOlZlcnNpb249IjIuMTAuNCIKICAgZGM6Rm9ybWF0PSJpbWFnZS9wbmciCiAgIHRpZmY6T3JpZW50YXRpb249IjEiCiAgIHhtcDpDcmVhdG9yVG9vbD0iR0lNUCAyLjEwIj4KICAgPGlwdGNFeHQ6TG9jYXRpb25DcmVhdGVkPgogICAgPHJkZjpCYWcvPgogICA8L2lwdGNFeHQ6TG9jYXRpb25DcmVhdGVkPgogICA8aXB0Y0V4dDpMb2NhdGlvblNob3duPgogICAgPHJkZjpCYWcvPgogICA8L2lwdGNFeHQ6TG9jYXRpb25TaG93bj4KICAgPGlwdGNFeHQ6QXJ0d29ya09yT2JqZWN0PgogICAgPHJkZjpCYWcvPgogICA8L2lwdGNFeHQ6QXJ0d29ya09yT2JqZWN0PgogICA8aXB0Y0V4dDpSZWdpc3RyeUlkPgogICAgPHJkZjpCYWcvPgogICA8L2lwdGNFeHQ6UmVnaXN0cnlJZD4KICAgPHhtcE1NOkhpc3Rvcnk+CiAgICA8cmRmOlNlcT4KICAgICA8cmRmOmxpCiAgICAgIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiCiAgICAgIHN0RXZ0OmNoYW5nZWQ9Ii8iCiAgICAgIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6MGJhZjI5YjEtNjE5Zi00ZTIwLWJiYTQtODY0MzY3ZTY5OGM2IgogICAgICBzdEV2dDpzb2Z0d2FyZUFnZW50PSJHaW1wIDIuMTAgKE1hYyBPUykiCiAgICAgIHN0RXZ0OndoZW49IjIwMTktMDUtMjRUMTY6MzA6NDUtMDQ6MDAiLz4KICAgIDwvcmRmOlNlcT4KICAgPC94bXBNTTpIaXN0b3J5PgogICA8cGx1czpJbWFnZVN1cHBsaWVyPgogICAgPHJkZjpTZXEvPgogICA8L3BsdXM6SW1hZ2VTdXBwbGllcj4KICAgPHBsdXM6SW1hZ2VDcmVhdG9yPgogICAgPHJkZjpTZXEvPgogICA8L3BsdXM6SW1hZ2VDcmVhdG9yPgogICA8cGx1czpDb3B5cmlnaHRPd25lcj4KICAgIDxyZGY6U2VxLz4KICAgPC9wbHVzOkNvcHlyaWdodE93bmVyPgogICA8cGx1czpMaWNlbnNvcj4KICAgIDxyZGY6U2VxLz4KICAgPC9wbHVzOkxpY2Vuc29yPgogIDwvcmRmOkRlc2NyaXB0aW9uPgogPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAKICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAogICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgIAo8P3hwYWNrZXQgZW5kPSJ3Ij8+f7yuRAAAAAZiS0dEAOAAVAAV1/8eJwAAAAlwSFlzAAAWJQAAFiUBSVIk8AAAAAd0SU1FB+MFGBQeLYv4W4oAAATVSURBVFjDrZhdiFVVFMd/59wzdyZI04lNrztBMPDFp0jFgiCj6YNqg2YvSQ/1VhD50Nc4YRBCQW8RVAiVI2wfiimdHgL7UOwhKwRFAvezG1JGy5k7997Ty9rD6nDuvWccL2z2mf2x9trr47/+ezJG/IIzmfWxlO9p4HlgPXAemLY+/hKcyYHM+tgLzmwH3gW2AgvAV9bHg7I/tz72h51X0PAXnDkK7FVD9wAPB2cesj6ekjW7gFOVNdPBmS3Wx71AOeqcfIQSLetjGZzZLcosAz0RvCjLDqst6XtR1vRkz57gzG6RVazFQpn029VYS/px6bcEZzbI931qLpO1yUX3A/NK5ppcdkN6bfJShOdKyXzIpbIaGatzmbrd1yKoDXSArrRSufC2/IYqZH3sSxxdAvbLcFss25Zb36UslK1VoUIFcCECy5rgblsfjwRn/pTgnhTLANwErgsUlKvI2pYySGl97AIUgiErAyMsdg44N+CAu5WLhyaKWL2nLkVwJgOyIgFVcOYR4AFgTAVsnYtziZ9z1sfjNUE+UiEB0M3AU8CdwBnr4zxQFgNAr6nZ54FnrI//iqJlAyt3gjMvAJ9XZB2zPu4tgjMHRZnuKm6ZMnA38CHwcoOMbcnB25QyHXWRPcGZi7nUppQhYxLoTVrKrKeDM2OCzsOwJimcPLGkMjbt25dLdjTBpEEHTEgcLCtF6qyc5iYriK+/1+dStZPG5SpaR/Zdtj5etT5eBS4rVyTQTJn3u/Q95fIka0nGzufA2+qm2SpaqmVvqpu+UVPL2sDJSkYi4ZFkTcjYO7n18TSwCzgr/OWGtH+kX6i069L/ATxuffw2OJML1/kOmBJrLABXgI+BZ5UiN6VfUPJ/BR60Pp7WIIVU7apvEy4lDFoCOuKi/5GuyvckcN36uFxJ7wlgnXJlz/p4LaF3MSAjSlFmwfq4WBE4JkE86lcCG4Mz43J4X9yTCnNt4GeK6R0WPtOSjNkAfGR9fFXW3AF8IOafkAB+y/o4J+UnFeMp4D1g0wAEzyrw0AcuAgesj6ey4MwO4Oea22XAJ9bHl0ShE8CjNbd6wvo4J2umgLk1FPuduRByTTtLsdAKdgRnnCjTqaGwh5TAQxUI6atW/VuPJ1kzhbwOdKpqYEsBvk2BYZXC3huc2Sh7NinOlNXEyaCylGRtzSXtqFCH9P33EKpbKiXHBA4Wa2Q1rYsACznwhRrsiluSxrMNDugD45LexxUadxu2ZSX/y9z6OAMcVYW1LZP7hZCNUihT868BJ1TRbNLGpM1aH2cKSdd9wZkjQtBuAN9YHy8Jde2MeCKtKGx9vAk8JkmwTc31RuDVWevjyURhMxE2L+8mzXn7IwRldcFqffSAXyXZywAK9W5vKcF9oZlN3m0Z0JWS8L4qlC1JimPWx9+CM+1hF1wh+Wqgd4tglsrBOuCVmvkDwZkXrY+f6bp5qw9FGrw2k+t6wDXFlbqK53wanNksVm/dDoWyhmuKChUeV0TuySZnNn3bLw+xVL/CAgddpglDGGmhpMAZNdarUNgL1sdrwmkuVGpZTyl0Zs3/bBCfZwIJCTxbFdp5QG15vUKHW+KFWevj9yKreztiCOvjPuAg8JdQ0x+AndbHH4XCtqyPPwE7ZO6KrJ2xPj7XNBb/A/TVH40E4+PXAAAAAElFTkSuQmCC'

// }

let unread_count = 0;
const slack_output = {};
const errors = [];

debug('Debugging');

if (process.argv.indexOf('--mark') > 0) {
	console.log('Mark as read');

	let token;
	for (let i = 3; i < process.argv.length; i++) {
		if (process.argv[i].indexOf('--token=') === 0) {
			token = process.argv[i].split('=')[1];
		}
	}
	if (!token) {
		console.log('Error: Missing token');
		return;
	}

	for (let i = 3; i < process.argv.length; i++) {
		let args = process.argv[i].split('=');
		if (args.length != 2) {
			continue;
		}
		if ([SLACK_CHANNELS, SLACK_GROUPS, SLACK_IM].indexOf(args[0]) < 0) {
			continue;
		}

		let channels = args[1].split(',');
		for (let j in channels) {
			console.log('/' + args[0] + SLACK_MARK + ' (' + channels[j] + ')');
			slack_request(args[0] + SLACK_MARK, {
				'token': token,
				'channel': channels[j],
				'ts': Math.floor(Date.now() / 1000)
			})
				.then((body) => {
					// console.log('  Success: ' + args[0] + ':' + channels[j]);
				});
		}
	}
	return;
}

function debug(message) {
	return DEBUG && console.log(message);
}

function slack_request(URL, query) {
	debug('  /' + URL + (query.channel ? ' (' + query.channel + ')' : ''));
	return request
		.get(SLACK_API + URL)
		.query(query)
		.then((res) => {
			if (res && res.body && res.body.ok === true) {
				return Promise.resolve(res.body);
			}
			return Promise.reject(res.body.error);
		})
		.catch((err) => {
			console.log("ERROR: " + '  /' + URL + (query.channel ? ' (' + query.channel + ')' : ''));
			errors.push(URL + ': ' + err + ' | color=red');
		});
}

function output() {
	unread_count = unread_count > 10 ? '10+' : unread_count > 0 ? unread_count : '';
	if (unread_count > 0) {
	    console.log(unread_count + ' | color=#e05415 ' + (SLACK_ICON_UNREAD));
	} else {
	    console.log(unread_count + ' | ' + (DARK_MODE ? SLACK_ICON_W : SLACK_ICON_B));
	}

	if (Object.keys(slack_output).length) {
		var unread = false;
		for (let i in slack_output) {
			let team = slack_output[i];

			// Only show team name if there are notifications for this team
			if (team.notifications.length > 0) {
				unread = true;
				console.log('---');
				console.log(team.name + ' | size=12');

				for (let j in team.notifications) {
					console.log(team.notifications[j]);
				}
				console.log('Mark all as read ' +
					'|bash=' + SCRIPT +
					' param1=--mark' +
					' param2=--token=' + team.token +
					(team.params[SLACK_IM] ? ' param3=' + SLACK_IM + '=' + team.params[SLACK_IM].join() : '') +
					(team.params[SLACK_GROUPS] ? ' param4=' + SLACK_GROUPS + '=' + team.params[SLACK_GROUPS].join() : '') +
					(team.params[SLACK_CHANNELS] ? ' param5=' + SLACK_CHANNELS + '=' + team.params[SLACK_CHANNELS].join() : '') +
					' refresh=true' +
					' terminal=false');
			}
		}
		
		if (unread != true) {
			console.log('---')
			// console.log('No unread Slack messages! | color=teal href=slack://')
			console.log('No unread Slack messages! | color=teal bash=' + __dirname + '/notifier/scripts/open-slack.sh terminal=false')
		}
	}
	if (errors.length > 0) {
		console.log('---');
		console.log('Errors');
		for (let i in errors) {
			console.log('--' + errors[i]);
		}
	}
}

function channel_output(channel) {
	unread_count += channel.count;

	let output_str = (channel.is_im ? '@' : '#') + channel.name;
	if (output_str.length > 15) {
		output_str = output_str.substring(0, 14) + '…';
	}
	output_str += ' '.repeat(17 - output_str.length);
	output_str += (channel.count > 10 ? '10+' : channel.count);

	let key = channel.is_im ? SLACK_IM : channel.is_channel ? SLACK_CHANNELS : SLACK_GROUPS;
	let href = 'slack://channel?team=' + channel.team + '&id=' + channel.id;

	slack_output[channel.token].notifications.push(output_str + '|font=Menlo size=13 href=' + href);
	slack_output[channel.token].notifications.push('Mark as read ' +
		'|alternate=true' +
		' font=Menlo size=13' +
		' bash=' + SCRIPT +
		' param1=--mark' +
		' param2=--token=' + channel.token +
		' param3=' + key + '=' + channel.id +
		' refresh=true' +
		' terminal=false');

	if (!slack_output[channel.token].params[key]) {
		slack_output[channel.token].params[key] = [];
	}
	slack_output[channel.token].params[key].push(channel.id);
}

async function run() {
	if (typeof tokens === 'undefined' || !tokens || !tokens.length) {
		errors.push('Missing Slack Legacy Token | color=red href=https://api.slack.com/custom-integrations/legacy-tokens');
		return output();
	}

	for (let i in tokens) {
		debug('Fetching channels for ' + tokens[i]);
		await get_team_notifications(tokens[i]);
	}
	output();
}

function get_team_notifications(token) {
	return get_team_info(token)
		.then((team) => {
			if (team) {
				slack_output[token] = {
					'id': team.id,
					'name': team.name,
					'token': token,
					'notifications': [],
					'params': {},
					'errors': []
				};
				return get_team_channels(token);
			}
		})
		.then((channels) => {
			return get_channels_info(channels, token);
		})
		.then((channels) => {
			return check_channels_unread(channels, token);
		})
		.then((channels) => {
			for (let i in channels) {
				if (channels[i]) {
					channel_output(channels[i]);
				}
			}
		});
}

function get_team_info(token) {
	return slack_request(SLACK_TEAM + SLACK_INFO, {
		'token': token
	})
		.then((body) => {
			if (body && body.team) {
				return Promise.resolve(body.team);
			}
		});
}

function get_team_channels(token) {
	return slack_request(SLACK_USER_CONVERSATIONS, {
		'token': token,
		'exclude_archived': true,
		'limit': 200,
		'types': 'public_channel,private_channel,mpim,im'
	})
		.then((body) => {
			if (body && body.channels) {
				return Promise.resolve(body.channels);
			}
		});
}

function get_user(user, token) {
	return slack_request(SLACK_USERS + SLACK_INFO, {
		'token': token,
		'user': user
	})
		.then((body) => {
			if (body && body.user) {
				return Promise.resolve(body.user);
			}
		});
}

function get_user_prefs(token) {
	return slack_request(SLACK_USERS + SLACK_PREFS, {
		'token': token
	})
		.then((body) => {
			if (body && body.prefs) {
				return Promise.resolve(body.prefs);
			}
		});
}

async function get_channels_info(channels, token) {
	let req = [];
	for (let i in channels) {
		let channel = channels[i];
		
		if (channel.is_im && channel.is_user_deleted) {
			continue;
		} else if (channel.is_group && !channel.is_open) {
			continue;
		}

		req.push(get_channel_info(channel, token));
	}
	return await Promise.all(req);
}

function get_channel_info(channel, token) {
	let url;
	if (channel.is_channel && channel.is_private) {
		url = SLACK_CONVERSATIONS;
		debug('Fetch private channel info for #' + channel.name + ' (' + channel.id + ')');
	} else if (channel.is_channel) {
		url = SLACK_CHANNELS;
		debug('Fetch channel info for #' + channel.name + ' (' + channel.id + ')');
	} else if (channel.is_group) {
		url = SLACK_GROUPS;
		debug('Fetch group info for #' + channel.name + ' (' + channel.id + ')');
	} else {
		url = SLACK_CONVERSATIONS;
		debug('Fetch conversation info for ' + channel.id);
	}
	return slack_request(url + SLACK_INFO, {
		'token': token,
		'channel': channel.id,
		'unreads': true
	})
		.then((body) => {
			if (body) {
				if (body.group) {
					body.channel = body.group;
				}
				if (body.channel) {
					body.channel.shared_team_ids = channel.shared_team_ids;
					return Promise.resolve(body.channel);
				}
			}
		});
}

async function check_channels_unread(channels, token) {
	let req = [];
	for (let i in channels) {
		if (channels[i]) {
			req.push(is_channel_unread(channels[i], token));
		}
	}
	return await Promise.all(req);
}

function is_channel_unread(channel, token) {
	// unread_count_display is a count of messages that the calling user has
	// yet to read that matter to them (this means it excludes things like
	// join/leave messages)
		
	if (channel && channel.unread_count_display > 0) {

		if (channel.is_im) {
			debug('Fetch user info for ' + channel.user);
			return get_user(channel.user, token)
				.then((user) => {
					if (user) {
						return Promise.resolve({
							'id': channel.id,
							'name': user.name,
							'count': channel.unread_count_display,
							'team': user.team_id,
							'is_im': true,
							'token': token
						});
					}
				});
		} else if (channel.is_member || channel.is_group) {
			let team = channel.shared_team_ids && channel.shared_team_ids.length > 0 ? channel.shared_team_ids[0] : '';
			return get_user_prefs(token)
				.then((user_prefs) => {
					if (user_prefs) {
						let muted = user_prefs.muted_channels.split(",");
						let is_muted = false;
						if (Array.isArray(muted)) {
							// console.log("multiple muted channels")
							if (muted.includes(String(channel.id))) {
								is_muted = true;
							}
						} else {
							// console.log("one muted channel")
							if (muted === channel.id) {
								is_muted = true;
							}
						}

						// console.log(muted)

						if (is_muted !== true) {
							return Promise.resolve({
								'id': channel.id,
								'name': channel.name,
								'count': channel.unread_count_display,
								'team': team,
								'is_channel': channel.is_member,
								'is_group': channel.is_group,
								'token': token
							});
						}
					}
				});
		}
	}
}

run();
