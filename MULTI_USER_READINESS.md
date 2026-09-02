# What Is Needed to Make VidzFlow a Real Multi-User Service

## The short version

VidzFlow is currently a working prototype for one person using one computer. It has the basic idea and much of the visible website, but it is not yet ready for many people to use at the same time.

VidzFlow will not require users to create accounts or passwords. It will use temporary anonymous job access instead. This keeps the service simple, but each visitor must keep the temporary link or browser data until their download is finished.

To make it a real public service, we must make sure that:

- one person's download cannot be seen or deleted by another person;
- many downloads can happen at the same time without crashing the website;
- large or abusive requests cannot use all the computer's resources;
- completed files are cleaned up instead of filling the disk;
- the service keeps working when something goes wrong; and
- the website, server, privacy rules and hosting all agree with one another.

## A simple comparison

Today, the app is like one shared office with one unlocked cabinet. Everyone can put things in the same cabinet, look through it, or empty it. That may be acceptable for a private experiment, but it is not acceptable for a public service.

A real service needs a separate, labeled space for each person's work, a receptionist who knows who is allowed to access each space, and a work queue so ten people do not all fight over one desk.

## What the current prototype already has

The project already contains:

- a website where a visitor can paste a media URL;
- pages for the home screen, privacy policy and terms of use;
- support for several media platforms;
- download and video-conversion logic; and
- a basic Flask web server.

These are useful foundations. They do not, by themselves, make the service safe for multiple users.

## What must be added before public launch

### 1. Private work areas

Every download needs its own private job space. A visitor should receive only the files created by that visitor's request.

The service must not show a single list containing everybody's files. A visitor must not be able to guess a URL and open somebody else's video.

### 2. A fair work queue

Downloading and converting videos can take a long time. Those tasks should happen in the background rather than keeping a website request open until the work finishes.

The visitor should see clear states such as:

- Waiting
- Downloading
- Converting
- Ready
- Failed

This allows the website to serve other people while one download is still running.

### 3. Limits for each visitor

The service needs reasonable limits, for example:

- how many downloads one person may start at once;
- how many URLs may be submitted together;
- the maximum playlist size;
- the maximum file size;
- how long a job may run; and
- how long finished files are kept.

Without limits, one person could accidentally or deliberately use all available storage, internet bandwidth or processing power.

### 4. Safe file handling

The service must carefully control where files are created and which files can be sent back. File names and folder names must never be trusted just because they came from a visitor or an outside platform.

Finished files should be identified by secure, temporary links rather than by exposing the computer's folder structure.

### 5. Anonymous job ownership, without accounts

Users will not create accounts, choose passwords or sign in. The service still needs a way to tell one visitor's work apart from another visitor's work.

When a visitor starts a download, the service should create a long, random, impossible-to-guess job token. The browser keeps that token and sends it only when asking for that job's status or files. The server checks the token on every request.

The token must not be the person's name, the original URL or a simple number such as `job-12`. It should expire automatically, for example after 30 minutes or after the file has been downloaded. A visitor must never be able to list all jobs or guess another visitor's token.

The visitor should be told clearly that:

- no account is created;
- the job is temporary;
- the download link must not be shared; and
- clearing browser data or losing the link may make the job inaccessible.

This is anonymous access, not permanent personal storage. If permanent download history or recovery is needed later, accounts would be required, but they are not part of this plan.

### 6. Automatic cleanup

Temporary and finished files must be removed automatically after a defined period. Failed downloads also need cleanup.

There should be a maximum storage allowance and an alert when storage, memory or processing capacity becomes unhealthy.

### 7. Reliable hosting

The app should run on a proper production server, not in development/debug mode. It also needs:

- HTTPS so visitors' connections are protected;
- a stable domain name;
- backups for important settings and records;
- monitoring and error alerts; and
- a plan for what happens when the server restarts.

If more than one server is used, they must share access to the job information and downloaded files.

### 8. Stronger URL and platform checks

Visitors should only be able to submit valid, supported URLs. The service must check the real website address instead of trusting a word found somewhere inside the text.

It should also prevent requests from being used to reach unrelated private systems on the internet.

### 9. Website and server agreement

Every button on the website must call a server action that actually exists. The home page, privacy page, terms page and all other advertised pages must work when opened through the running service.

This needs a simple full-user test: open the site, submit a permitted public URL, wait for the result, download it, open the privacy and terms pages, and try the same process from two browser windows at once.

### 10. Legal and trust preparation

Before inviting the public, the owner should confirm:

- that downloading the supported content is allowed in the intended countries;
- that users are told they are responsible for having permission to use content;
- what information is stored and for how long;
- how users can report abuse or copyright concerns; and
- who is responsible for operating the service.

The privacy policy and terms page should describe the real behavior of the finished service, not only the prototype.

## A practical order of work

### Stage 1: Make the current prototype dependable

- Make every visible page and button work.
- Fix the website/server endpoint agreement.
- Add basic limits and friendly error messages.
- Turn off debug mode for any shared or public test.
- Add tests for the main download journey.

### Stage 2: Protect people from one another

- Give every request a private job space.
- Add anonymous job tokens and ownership checks.
- Remove the global file browser and global delete action.
- Add automatic cleanup.
- Test two or more simultaneous downloads.

### Stage 3: Handle real traffic

- Add a background work queue.
- Add per-visitor limits and rate controls.
- Add monitoring, logs and alerts.
- Store files in storage designed for service use.
- Test restarts, failed downloads and full storage.

### Stage 4: Prepare for public use

- Use secure hosting and HTTPS.
- Review the privacy and terms pages.
- Decide on support and abuse-reporting processes.
- Run a small private trial before opening the service to everyone.

## How we know it is real

The service is ready for a public launch only when a small trial can demonstrate all of the following:

1. Two people can download at the same time without creating accounts.
2. Neither person's temporary token can access the other's files.
3. Neither person can list, change or delete another person's job.
4. A failed or cancelled download does not leave the system unusable.
5. Large requests are limited fairly.
6. Old files and expired tokens disappear automatically.
7. The service survives a restart without losing track of active work.
8. The privacy and terms pages describe anonymous temporary jobs accurately.
9. Operators can see errors and know when the service needs attention.

That is the difference between a promising website on one computer and a dependable service that real people can safely use.
