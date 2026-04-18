# PRD: CineAlert

Version: 1.0  
Date: April 18, 2026  
Status: Draft  
Forked from: [github.com/CreatorSky/cineplex-notifier](http://github.com/CreatorSky/cineplex-notifier)  
Repo: https://github.com/rahulkahani/cinealert.git

1. ## Overview

2. The CineAlert is a Dockerized Python application that monitors [Cineplex.com](http://Cineplex.com) for IMAX 70mm ticket availability at a specific theatre location. When tickets become available for purchase, it sends an SMS alert to the user with the movie name, format, location, and a direct link to purchase tickets. The application is forked from the open-source cineplex-notifier project (MIT License) and rebuilt to support multiple movies, specific format targeting (IMAX 70mm), location-specific monitoring (Cineplex Cinemas Vaughan), and a simplified urgent alert system via email-to-SMS.

## 2\. Problem Statement

IMAX 70mm screenings are rare and highly sought after. Major film releases like The Odyssey (Christopher Nolan, July 17, 2026\) and Dune: Part 3 (Denis Villeneuve, December 18, 2026\) are expected to offer IMAX 70mm presentations at select locations. Cineplex Cinemas Vaughan (3555 Highway 7 West, Vaughan, ON) is a target location that supports IMAX screenings. The problem is that IMAX 70mm tickets at premium locations often sell out within hours of going on sale, and Cineplex provides no built-in alert system for format-specific ticket availability. Users must manually check the website repeatedly or risk missing out entirely. This tool solves that by automating the monitoring and delivering an instant SMS alert the moment IMAX 70mm tickets become purchasable.

3. ## Goals

4. G1: Monitor multiple Cineplex movie pages simultaneously for IMAX 70mm ticket availability.  
5. G2: Target a specific theatre location (Cineplex Cinemas Vaughan, Ontario).  
6. G3: Detect when IMAX 70mm format tags appear on a movie’s listing, indicating tickets are on sale or imminent.  
7. G4: Send a clear, urgent SMS alert with the movie name, format, theatre, and a direct purchase link.  
8. G5: Prevent duplicate alerts by tracking notification state across polling cycles.  
9. G6: Run autonomously as a lightweight Docker container with minimal resource usage (no Selenium/Chrome dependency).  
10. G7: Be easily configurable to add new movies or change theatre/format targets via a JSON config file.

## 4\. Target Movies (Initial Scope)

Movie 1: The Odyssey

- Cineplex URL: [https://www.cineplex.com/movie/the-odyssey](https://www.cineplex.com/movie/the-odyssey)  
-   \- Cineplex Movie ID: 37617  
-   \- Release Date: July 17, 2026  
-   \- Director: Christopher Nolan  
-   \- Current Status: Page live, “Get Advance Tickets” button present, no IMAX 70mm showtimes yet  
-   \- Current Formats: \[2, 3\] (no 70mm format ID present yet)  
-   \- Poster URL: [https://mediafiles.cineplex.com/Central/Film/Posters/37617\_320\_470.jpg](https://mediafiles.cineplex.com/Central/Film/Posters/37617_320_470.jpg)

Movie 2: Dune: Part 3

- Cineplex URL: [https://www.cineplex.com/movie/dune-part-3](https://www.cineplex.com/movie/dune-part-3)  
-   \- Cineplex Movie ID: 37998  
-   \- Release Date: December 18, 2026  
-   \- Director: Denis Villeneuve  
-   \- Current Status: Page live, “Get Advance Tickets” button present, no showtimes yet  
-   \- Current Formats: \[\] (empty, no format IDs assigned yet)  
-   \- Poster URL: [https://mediafiles.cineplex.com/Central/Film/Posters/37998\_320\_470.jpg](https://mediafiles.cineplex.com/Central/Film/Posters/37998_320_470.jpg)

Target Theatre: Cineplex Cinemas Vaughan

- Address: 3555 Highway 7 West, Vaughan, ON, L4L 6B1  
-   \- Phone: (905) 851-1001  
-   \- Supported Formats: Regular, VIP, IMAX, Recliner, UltraAVX  
-   \- Theatre URL: [https://www.cineplex.com/theatre/cineplex-cinemas-vaughan](https://www.cineplex.com/theatre/cineplex-cinemas-vaughan)

Target Format: IMAX 70mm

- Cineplex vistaAttribute for IMAX: “IMAX”  
-   \- Cineplex vistaAttribute for 70mm: “70MM”  
-   \- Both attributes must be present on a showtime to trigger an alert

## 5\. Functional Requirements

FR-1: Multi-Movie Monitoring  
The application shall read a list of movies from a config.json file and monitor each one on every polling cycle. Each movie entry includes the Cineplex slug, display name, and the direct ticket purchase URL. Adding or removing movies requires only editing the config file and restarting the container.

FR-2: Cineplex Page Scraping via [Next.js](http://Next.js) Data Extraction  
The application shall fetch each movie’s Cineplex page using an HTTP GET request (no browser/Selenium required). It shall parse the HTML response to extract the embedded \_\_NEXT\_DATA\_\_ JSON object from the script tag with id=”\_\_NEXT\_DATA\_\_”. From this JSON, it shall extract the movieDetails object containing: movie name, release date, formats array, hasShowtimes boolean, poster URLs, and slug.

FR-3: IMAX 70mm Format Detection  
The application shall check the movie’s formats array and the showtime experience attributes for the presence of IMAX (vistaAttribute: “IMAX”) and 70mm (vistaAttribute: “70MM”) at the target theatre. The detection operates in two stages:  
  Stage 1 \- Format Watch: Monitor the movieDetails.formats array for the addition of format IDs that correspond to IMAX or 70mm. When new format IDs appear, this is an early signal that those screenings are being configured.  
  Stage 2 \- Showtime Watch: Monitor for actual showtime listings at Cineplex Cinemas Vaughan that carry both the IMAX and 70MM experience tags. This confirms tickets are purchasable.

FR-4: Location-Specific Filtering  
The application shall only trigger alerts when the target format is available at the configured theatre (Cineplex Cinemas Vaughan). Availability at other Cineplex locations shall be ignored.

FR-5: SMS Alert Delivery  
When IMAX 70mm availability is detected, the application shall send an SMS via the email-to-SMS gateway method (Gmail SMTP to carrier gateway address). The alert shall be sent to all configured phone numbers.

FR-6: Alert Message Format  
The SMS message shall follow this exact template:

TICKETS LIVE: \[Movie Name\]  
IMAX 70mm @ Cineplex Vaughan  
Tickets are selling fast \- book now before they sell out\!  
\[Direct Purchase URL\]

Example for The Odyssey:

TICKETS LIVE: The Odyssey  
IMAX 70mm @ Cineplex Vaughan  
Tickets are selling fast \- book now before they sell out\!  
[https://www.cineplex.com/movie/the-odyssey?openTM=true](https://www.cineplex.com/movie/the-odyssey?openTM=true)

The message shall be plain text, under 320 characters, with no images or HTML.

FR-7: Duplicate Alert Prevention  
The application shall maintain a state.json file that records which alerts have been sent (keyed by movie slug and alert type). Once an alert is sent for a movie, the same alert shall not be sent again on subsequent polling cycles. The state file persists across container restarts via a Docker volume mount.

FR-8: Polling Schedule  
The application shall run on a cron schedule of every 15 minutes (\*/15 \* \* \* \*). This balances responsiveness with not overloading the Cineplex server.

FR-9: Error Handling and Logging  
The application shall log all activity (checks, detections, alerts sent, errors) to a log file with timestamps. If a movie page returns a non-200 status code or the \_\_NEXT\_DATA\_\_ structure changes, the application shall log the error and continue to the next movie without crashing. Network timeouts shall be handled gracefully with a 30-second timeout per request.

## 6\. Technical Architecture

6.1 Technology Stack

- Language: Python 3.10+  
-   \- HTTP Client: requests library  
-   \- HTML Parser: BeautifulSoup4  
-   \- SMTP: Python smtplib (Gmail SMTP with SSL)  
-   \- Scheduler: Linux cron (inside Docker)  
-   \- Containerization: Docker with docker-compose  
-   \- Config: JSON file  
-   \- State Persistence: JSON file (Docker volume mounted)

6.2 File Structure

cinealert/  
  Config.json            \- Movie list, theatre, format, phone config  
  [main.py](http://main.py)                \- Entry point, orchestration loop  
  utils/  
    [scraper.py](http://scraper.py)           \- Fetches Cineplex page, extracts \_\_NEXT\_DATA\_\_  
    [alert.py](http://alert.py)             \- Composes and sends SMS via email-to-SMS  
    [state.py](http://state.py)             \- Reads/writes state.json for duplicate prevention  
  providers/  
    Sms\_gateways.py      \- Canadian carrier SMS gateway domains (kept from original)  
  State.json             \- Auto-generated alert state tracking  
  Dockerfile             \- Lightweight Python image (no Chrome)  
  Docker-compose.yml     \- Container config with volume mount  
  Makefile               \- build, run, stop, purge commands  
  [entrypoint.sh](http://entrypoint.sh)          \- Loads env vars and starts cron  
  [run.sh](http://run.sh)                 \- Cron-invoked script that calls [main.py](http://main.py)  
  Requirements.txt       \- requests, beautifulsoup4  
  [README.md](http://README.md)              \- Setup and usage documentation

6.3 Data Flow

1. Cron fires every 15 minutes, executes [run.sh](http://run.sh)  
2.   2\. [run.sh](http://run.sh) calls [main.py](http://main.py)  
3.   3\. [main.py](http://main.py) reads config.json for movie list  
4.   4\. For each movie, [main.py](http://main.py) calls scraper.fetch\_movie\_data(slug)  
5.   5\. [scraper.py](http://scraper.py) makes HTTP GET to [https://www.cineplex.com/movie/{slug](https://www.cineplex.com/movie/{slug)}  
6.   6\. [scraper.py](http://scraper.py) parses HTML, extracts \_\_NEXT\_DATA\_\_ JSON  
7.   7\. [scraper.py](http://scraper.py) returns structured data: movie name, formats, hasShowtimes, etc.  
8.   8\. [main.py](http://main.py) evaluates formats for IMAX \+ 70MM presence  
9.   9\. [main.py](http://main.py) checks state.json to see if alert already sent  
10.   10\. If new detection and not already alerted: [main.py](http://main.py) calls alert.send\_sms()  
11.   11\. [alert.py](http://alert.py) composes the urgent message with movie name and purchase link  
12.   12\. [alert.py](http://alert.py) sends email via Gmail SMTP to carrier SMS gateway address  
13.   13\. User receives SMS on phone  
14.   14\. [main.py](http://main.py) updates state.json to record the alert was sent  
15.   15\. [main.py](http://main.py) moves to next movie in config, repeats steps 4-14

6.4 Cineplex Data Structure (as discovered via site analysis)  
The Cineplex website is built on [Next.js](http://Next.js). Each movie page contains a script tag with id=”\_\_NEXT\_DATA\_\_” that holds a JSON object. The relevant data path is:  
  props.pageProps.movieDetails \- contains movie metadata  
  props.pageProps.movieDetails.formats \- array of integer format IDs  
  props.pageProps.movieDetails.hasShowtimes \- boolean  
  [props.pageProps.movieDetails.name](http://props.pageProps.movieDetails.name) \- display title  
  props.pageProps.movieDetails.slug \- URL slug  
  props.pageProps.movieDetails.releaseDate \- ISO date string  
  props.pageProps.movieDetails.mediumPosterImageUrl \- poster image

Cineplex experience/format definitions found in page data:  
  “IMAX” \-\> vistaAttribute: “IMAX” (contentID: 254628\)  
  “70mm” \-\> vistaAttribute: “70MM” (contentID: 254640\)  
  “IMAX 3D” \-\> vistaAttribute: “IMAX\_3D” (contentID: 270248\)  
  “UltraAVX” \-\> vistaAttribute: “AVX” (contentID: 254620\)  
  “Regular” \-\> vistaAttribute: “REGULAR” (contentID: 254644\)  
  “Recliner” \-\> vistaAttribute: “RECLINER” (contentID: 254638\)  
  “4DX” \-\> vistaAttribute: “4DX” (contentID: 254630\)  
  “D-BOX” \-\> vistaAttribute: “D-BOX” (contentID: 254636\)

## 7\. Configuration Specification

The config.json file defines all runtime parameters. Example:

{  
  “Theatre”: “cineplex-cinemas-vaughan”,  
  “Theatre\_display\_name”: “Cineplex Vaughan”,  
  “Target\_formats”: \[“IMAX”, “70MM”\],  
  “Poll\_interval\_minutes”: 15,  
  “Movies”: \[  
    {  
      “Slug”: “the-odyssey”,  
      “Name”: “The Odyssey”,  
      “Ticket\_url”: “[https://www.cineplex.com/movie/the-odyssey?openTM=true](https://www.cineplex.com/movie/the-odyssey?openTM=true)”  
    },  
    {  
      “Slug”: “dune-part-3”,  
      “Name”: “Dune: Part 3”,  
      “Ticket\_url”: “[https://www.cineplex.com/movie/dune-part-3?openTM=true](https://www.cineplex.com/movie/dune-part-3?openTM=true)”  
    }  
  \]  
}

Environment variables (set in docker-compose.yml):  
  EMAIL: Gmail address used as SMTP sender  
  PASSWORD: Gmail app password (generated at [https://support.google.com/accounts/answer/185833](https://support.google.com/accounts/answer/185833))  
  PHONE: Phone number and carrier pairs, comma-separated (e.g., “5551234567:Rogers,5559876543:Bell”)

## 8\. Deployment and Usage

Prerequisites: Docker, Make, a Gmail account with an app password.

Setup Steps:

1. Clone the repo: git clone https://github.com/rahulkahani/cinealert.git  
2. 2\. Cd cinealert  
3.   3\. Edit config.json with desired movies and theatre  
4.   4\. Edit docker-compose.yml with EMAIL, PASSWORD, and PHONE values  
5.   5\. Run: make build  
6.   6\. Run: make run  
7.   7\. The container runs in the background, checking every 15 minutes  
8.   8\. To stop: make stop  
9.   9\. To remove: make purge

The state.json file is volume-mounted so alert history survives container restarts. Logs are written to /app/logs/main.log inside the container.

## 9\. Risks and Mitigations

R1: Cineplex changes their site structure or removes \_\_NEXT\_DATA\_\_  
  Likelihood: Low-Medium. [Next.js](http://Next.js) sites typically maintain this pattern.  
  Mitigation: The scraper should validate that the expected JSON structure exists before parsing. Log warnings if the structure changes. The code should be modular enough to swap in a Selenium fallback if needed.

R2: Cineplex blocks or rate-limits automated requests  
  Likelihood: Low. Polling once every 15 minutes from a single IP is very low volume.  
  Mitigation: Use a realistic User-Agent header. Add a random delay (0-60 seconds) before each request to avoid exact 15-minute intervals. Respect robots.txt if applicable.

R3: IMAX 70mm is not offered at Vaughan for these films  
  Likelihood: Medium. Not all IMAX locations receive 70mm prints.  
  Mitigation: The config supports changing the theatre target. The user can add addipolicies  
  Likelihood: Low, if using an app password correctly.  
  Mitigation: Use a dedicated Gmail account for this application. Follow Google’s app password setup guide. Monitor logs for SMTP authentication errors.

10. ## Success Criteria

11. SC-1: The user receives an SMS within 15 minutes of IMAX 70mm tickets becoming available at Cineplex Vaughan.  
12. SC-2: The SMS contains the correct movie name, format, location, and a working purchase link.  
13. SC-3: The user does not receive duplicate alerts for the same movie after the initial notification.  
14. SC-4: The application runs continuously for weeks/months without crashing or requiring manual intervention.  
15. SC-5: Adding a new movie to monitor requires only editing config.json and restarting the container (under 2 minutes of user effort).  
16. SC-6: The Docker image builds and runs successfully on any machine with Docker installed.  
17. SC-7: The user successfully purchases IMAX 70mm tickets before they sell out, made possible by the early alert.  
18. 

19. ## 11\. Future Enhancements (Out of Scope for V1)

20. The following are not included in V1 but could be added in future iterations:  
21.   \- Twilio MMS support for sending alerts with movie poster images  
22.   \- Telegram or Discord bot as an alternative notification channel  
23.   \- Web dashboard to view monitoring status and alert history  
24.   \- Support for multiple theatre locations per movie (e.g., Vaughan \+ Scotiabank Toronto)  
25.   \- Automatic seat selection and cart-hold (would require Selenium \+ authenticated session)  
26.   \- Price tracking and price-drop alerts  
27.   \- Support for other Canadian cinema chains (Landmark, Imagine)  
28.   \- Showtime detail extraction (specific dates and times in the alert)  
29.   \- Health check endpoint for monitoring container status  
30. 

31. ## 12\. Timeline

32. Phase 1 \- Core Build (Target: 1-2 days)  
33.   \- Fork repo and set up new file structure  
34.   \- Implement [scraper.py](http://scraper.py) with \_\_NEXT\_DATA\_\_ extraction  
35.   \- Implement [alert.py](http://alert.py) with email-to-SMS urgent message  
36.   \- Implement [state.py](http://state.py) for duplicate prevention  
37.   \- Rewrite [main.py](http://main.py) orchestration loop  
38.   \- Create config.json with Odyssey and Dune: Part 3  
39.   \- Update Dockerfile (remove Chrome/Selenium dependencies)  
40.   \- Update requirements.txt  
41.   
42. Phase 2 \- Testing (Target: 1 day)  
43.   \- Test scraper against live Cineplex pages for both movies  
44.   \- Test SMS delivery to your phone and carrier  
45.   \- Test duplicate prevention across multiple runs  
46.   \- Test error handling with invalid URLs and network failures  
47.   \- Verify Docker build and run cycle  
48.   
49. Phase 3 \- Deploy and Monitor (Ongoing)  
50.   \- Deploy container and let it run  
51.   \- The Odyssey (July 17): IMAX 70mm tickets likely to appear May-June 2026  
52.   \- Dune: Part 3 (Dec 18): IMAX 70mm tickets likely to appear October-November 2026  
53.   \- Monitor logs periodically to confirm the scraper is running correctly  
54.   \- Adjust config if theatre or format targets changetional theatre locations as fallbacks (e.g., Scotiabank Theatre Toronto, which is a known IMAX 70mm venue).

R4: The format ID mapping changes or 70mm is tagged differently  
  Likelihood: Low. The vistaAttribute “70MM” appears stable in the Cineplex data.  
  Mitigation: The scraper should also do a text-based search for “70mm” or “70MM” in the raw page data as a backup detection method.

R5: Email-to-SMS gateway becomes unreliable or carrier drops support  
  Likelihood: Low-Medium. Some carriers have quietly deprecated these gateways.  
  Mitigation: Test with your carrier before deploying long-term. If SMS delivery fails, the error is logged. A future enhancement could add Twilio or Telegram as an alternative notification channel.

R6: Gmail blocks SMTP sending due to security 