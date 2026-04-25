"""
Web tools — search, fetch pages, and global news briefings.
"""

import httpx
import xml.etree.ElementTree as ET
import asyncio  # Required for parallel execution
import re

SEED_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://www.aljazeera.com/xml/rss/all.xml'
]

async def fetch_and_parse_feed(client, url):
    """Helper function to handle a single feed request and parse its XML."""
    try:
        response = await client.get(url, headers={'User-Agent': 'Friday-AI/1.0'}, timeout=5.0)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        # Extract source name from URL (e.g., 'BBC' or 'NYTIMES')
        parts = url.split('.')
        source_name = parts[1].upper() if len(parts) > 1 else url
        
        feed_items = []
        # Get top 5 items per feed
        items = root.findall(".//item")[:5]
        for item in items:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            
            if description:
                description = re.sub('<[^<]+?>', '', description).strip()

            feed_items.append({
                "source": source_name,
                "title": title,
                "summary": description[:200] + "..." if description else "",
                "link": link
            })
        return feed_items
    except Exception:
        # If one feed fails, return an empty list so others can still succeed
        return []

def register(mcp):

    @mcp.tool()
    async def get_world_news() -> str:
        """
        Fetches the latest global headlines from major news outlets simultaneously.
        Use this when the user asks 'What's going on in the world?' or for recent events.
        """
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            # 1. Create a list of 'tasks' (one for each URL)
            tasks = [fetch_and_parse_feed(client, url) for url in SEED_FEEDS]
            
            # 2. Fire them all at once and wait for the results
            # results will be a list of lists: [[news from bbc], [news from nyt], ...]
            results_of_lists = await asyncio.gather(*tasks)
            
            # 3. Flatten the list of lists into a single list of articles
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The global news grid is unresponsive, sir. I'm unable to pull headlines."

        # 4. Format the final briefing
        report = ["### GLOBAL NEWS BRIEFING (LIVE)\n"]
        # Limit to top 12 items so the AI doesn't get overwhelmed
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @mcp.tool()
    async def get_weather(city: str) -> str:
        """Get current weather for a city."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                geo = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1}
                )
                geo.raise_for_status()
                results = geo.json().get("results")
                if not results:
                    return f"City '{city}' not found."
                loc = results[0]
                weather = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": loc["latitude"],
                        "longitude": loc["longitude"],
                        "current": "temperature_2m,weathercode,windspeed_10m,relative_humidity_2m",
                        "timezone": "auto"
                    }
                )
                weather.raise_for_status()
                cur = weather.json()["current"]
                codes = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
                         45:"Foggy",48:"Icy fog",51:"Light drizzle",61:"Slight rain",
                         63:"Moderate rain",65:"Heavy rain",71:"Slight snow",80:"Rain showers",
                         95:"Thunderstorm"}
                condition = codes.get(cur["weathercode"], f"Code {cur['weathercode']}")
                return (f"{city}: {condition}, {cur['temperature_2m']}°C, "
                        f"humidity {cur['relative_humidity_2m']}%, "
                        f"wind {cur['windspeed_10m']} km/h")
        except Exception as e:
            return f"Weather unavailable: {e}"

    @mcp.tool()
    async def search_web(query: str) -> str:
        """Search the web for a given query and return a summary of results."""
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query, max_results=5)
            if not results:
                return f"No results found for: {query}"
            lines = []
            for r in results:
                lines.append(f"{r['title']}: {r['body']}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"Search failed: {e}"

    @mcp.tool()
    async def fetch_url(url: str) -> str:
        """Fetch the raw text content of a URL."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text[:4000]
    
    @mcp.tool()
    async def open_world_monitor() -> str:
        """
        Opens the World Monitor dashboard (worldmonitor.app) in the system's web browser.
        Use this when the user wants a visual overview of global events or a real-time map.
        """
        import webbrowser
        url = "https://worldmonitor.app/"
        
        try:
            # This opens the URL in the default browser (Chrome/Edge/Safari)
            webbrowser.open(url)
            return "Displaying the World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"I'm unable to initialize the visual monitor: {str(e)}"