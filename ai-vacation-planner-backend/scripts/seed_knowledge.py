"""
seed_knowledge.py

Populates the travel knowledge base with sample travel guides for key
destinations. Run this script once after setting up the project to give
the RAG pipeline useful context before generating itineraries.

Usage:
    cd ai-vacation-planner-backend
    python scripts/seed_knowledge.py
"""

import asyncio

from app.services.knowledge_service import add_document

DOCUMENTS: list[dict[str, str]] = [
    {
        "destination": "Paris",
        "source": "guide",
        "content": (
            "Paris, the capital of France, is one of the world's most visited "
            "cities. The Eiffel Tower, built in 1889, offers panoramic views "
            "from its summit. The Louvre Museum houses the Mona Lisa and is "
            "the world's largest art museum. Montmartre is a historic hilltop "
            "neighbourhood known for the Sacre-Coeur Basilica and its "
            "bohemian artistic heritage. Notre Dame Cathedral, a Gothic "
            "masterpiece on the Ile de la Cite, remains a must-see landmark "
            "despite ongoing restoration. Seine River cruises offer scenic "
            "views of the city's bridges and monuments, especially after "
            "dark. Hidden gems include the Promenade Plantee, an elevated "
            "park built on a disused railway line, the covered passage "
            "Galerie Vivienne with its historic boutiques, and Canal "
            "Saint-Martin, a trendy area popular with locals for canal-side "
            "picnics. Local food highlights include flaky croissants, "
            "delicate crepes from street stalls, hearty French onion soup, "
            "and classic neighbourhood bistros serving steak frites. Budget "
            "travellers should note that many museums, including the "
            "Louvre, offer free entry on the first Sunday of certain months "
            "for under-26 EU residents, and a picnic at Champ de Mars "
            "beneath the Eiffel Tower is a free way to enjoy the view. The "
            "Paris Metro offers an affordable day pass covering unlimited "
            "travel across the city's extensive network."
        ),
    },
    {
        "destination": "Tokyo",
        "source": "guide",
        "content": (
            "Tokyo, Japan's capital, blends ancient tradition with "
            "futuristic energy. Senso-ji in Asakusa is Tokyo's oldest "
            "temple, approached through the lively Nakamise shopping "
            "street. Shibuya Crossing is the world's busiest pedestrian "
            "intersection, best viewed from a nearby cafe. Meiji Shrine "
            "offers a peaceful forested escape near bustling Harajuku. "
            "Shinjuku is known for its neon-lit nightlife district and the "
            "free observation deck at the Metropolitan Government Building. "
            "Hidden gems include Yanaka, a preserved old-town neighbourhood "
            "with traditional shops and temples that survived WWII, "
            "Shimokitazawa, a bohemian district loved for vintage clothing "
            "and live music venues, and Hamarikyu Gardens, an underrated "
            "traditional garden with a teahouse surrounded by skyscrapers. "
            "Food highlights include conveyor belt sushi restaurants, "
            "steaming bowls of ramen, standing sushi bars for cheap fresh "
            "fish, and the Tsukiji Outer Market for breakfast seafood. "
            "Budget tips include the Tokyo Metro day pass for unlimited "
            "affordable rides, and convenience store meals like onigiri "
            "and bento boxes for a quick cheap bite. The immersive teamLab "
            "digital art museums are a uniquely Tokyo experience worth the "
            "splurge."
        ),
    },
    {
        "destination": "Barcelona",
        "source": "guide",
        "content": (
            "Barcelona, the capital of Catalonia, is famed for Gaudi's "
            "surreal architecture. The Sagrada Familia basilica, still "
            "under construction after over a century, dominates the "
            "skyline. Park Guell offers whimsical mosaic terraces and "
            "skyline views. The Gothic Quarter's narrow medieval streets "
            "lead to the Barcelona Cathedral and hidden plazas. La "
            "Boqueria market near Las Ramblas overflows with fresh "
            "produce, tapas stalls, and fresh juice. Barceloneta beach "
            "provides a lively seaside escape with beach bars. Hidden gems "
            "include the Poblenou neighbourhood with its converted "
            "industrial lofts and street art, the Bunkers del Carmel "
            "viewpoint offering a panoramic 360-degree city view popular "
            "with locals at sunset, and the El Born district's boutiques "
            "and the Santa Maria del Mar basilica. Food highlights include "
            "tapas bars, patatas bravas, pan con tomate, and the local "
            "vermouth culture at old-school vermuterias. Budget tips: the "
            "Sagrada Familia exterior can be admired for free, the city's "
            "beaches are free to enjoy, and the Picasso Museum offers free "
            "entry on Sunday afternoons and the first Sunday of the month."
        ),
    },
    {
        "destination": "New York",
        "source": "guide",
        "content": (
            "New York City is a dense mix of iconic landmarks and diverse "
            "neighbourhoods. Central Park offers a huge green escape in "
            "the middle of Manhattan, while Times Square dazzles with "
            "billboards and crowds. The Brooklyn Bridge offers a free "
            "scenic walk between boroughs with skyline views. The "
            "Metropolitan Museum of Art houses one of the world's great "
            "art collections. Hidden gems include The High Line, an "
            "elevated park built on a former rail line, Roosevelt Island's "
            "quiet tram ride and skyline views, the Smorgasburg food "
            "market in Brooklyn on weekends, and the cobblestoned Dumbo "
            "neighbourhood beneath the Manhattan Bridge. Food highlights "
            "include cheap dollar pizza slices, classic New York bagels, "
            "old-school delis, and the many food halls scattered across "
            "Manhattan and Brooklyn. Budget tips: the Staten Island Ferry "
            "is free and offers views of the Statue of Liberty, several "
            "major museums have free or pay-what-you-wish days, and a "
            "CityPASS can save money for visitors planning multiple paid "
            "attractions. The subway offers an affordable unlimited-ride "
            "day pass, the best way to get around the five boroughs."
        ),
    },
    {
        "destination": "Rome",
        "source": "guide",
        "content": (
            "Rome, Italy's capital, is an open-air museum of ancient "
            "history. The Colosseum, once home to gladiator battles, "
            "remains the city's most iconic ruin. The Vatican Museums "
            "house an extraordinary collection culminating in the Sistine "
            "Chapel. The Trevi Fountain and the Spanish Steps are lively "
            "meeting points day and night. The Pantheon, a remarkably "
            "preserved ancient temple, is free to enter on weekdays. "
            "Hidden gems include Trastevere, a charming cobblestoned "
            "neighbourhood full of trattorias and nightlife, the Aventine "
            "Hill keyhole view offering a perfectly framed glimpse of St "
            "Peter's Basilica dome through a garden gate, and the "
            "Testaccio market, a local favourite for authentic Roman food "
            "away from the tourist crush. Food highlights include "
            "carbonara, cacio e pepe, fried supplì rice balls, artisanal "
            "gelato, and standing espresso at the counter, Roman-style. "
            "Budget tips: entry to the city's basilicas is free, the "
            "Pantheon is free on weekdays, and the public nasoni drinking "
            "fountains scattered across the city provide free cold water. "
            "Walking is the best way to explore central Rome, since most "
            "major sights sit within strolling distance of each other."
        ),
    },
]


async def seed() -> None:
    """Add every document in DOCUMENTS to the knowledge base, printing
    progress per destination and a final summary.

    Errors adding an individual document are caught and reported so that
    one bad document does not stop the rest of the seed run.
    """
    seeded_count = 0
    for doc in DOCUMENTS:
        destination = doc["destination"]
        try:
            chunks_stored = await add_document(
                destination=destination,
                content=doc["content"],
                source=doc["source"],
            )
            print(f"Seeding {destination}... {chunks_stored} chunks stored")
            seeded_count += 1
        except Exception as e:
            print(f"Failed to seed {destination}: {e}")

    print(f"Done. Seeded {seeded_count} destinations.")


if __name__ == "__main__":
    asyncio.run(seed())
