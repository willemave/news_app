This is a new app. The goal of this app is to scrape top news sites, rss feeds and pod casts. 

Technologies
1. Python
2. Pydantic for all models
3. SQLite for local sql database
4. HTMX for simple html rendering. 

Structure
1. app/scraping/ -- this is the main place to implement new scrapers. 
2. app/routers/ -- these are the routes for the web app
