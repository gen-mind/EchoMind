#!/usr/bin/env python3
"""
TensorBoard Projector Test Script

Quick test of the TensorBoard Projector API endpoints.
"""

import os
import sys
import json
import webbrowser
from typing import Optional

try:
    import requests
except ImportError:
    print("❌ Error: requests library not found")
    print("Install with: pip install requests")
    sys.exit(1)


# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.demo.echomind.ch")
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "")  # Set this!


def get_headers() -> dict:
    """Get HTTP headers with Bearer token."""
    if not BEARER_TOKEN:
        print("❌ Error: BEARER_TOKEN not set")
        print("Set with: export BEARER_TOKEN='your-token-here'")
        sys.exit(1)

    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }


def load_stats() -> dict:
    """Load collection statistics."""
    print("📊 Loading statistics...")

    url = f"{API_BASE_URL}/api/v1/projector/stats"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()

    print("\n✅ Statistics:")
    print(f"  User Collection:  {data['user_collection']}")
    print(f"  User Vectors:     {data['user_vectors']:,}")
    print(f"  Org Collection:   {data['org_collection']}")
    print(f"  Org Vectors:      {data['org_vectors']:,}")

    if data.get('teams'):
        print(f"\n  Teams:")
        for team in data['teams']:
            print(f"    {team['team_name']} ({team['collection_name']}): {team['vector_count']:,} vectors")

    return data


def generate_visualization(
    scope: str,
    search_query: Optional[str] = None,
    team_id: Optional[int] = None,
    org_id: Optional[int] = None,
    limit: int = 10000,
    open_browser: bool = True
) -> dict:
    """
    Generate TensorBoard visualization.

    Args:
        scope: 'user', 'team', or 'org'
        search_query: Optional keyword filter
        team_id: Required for team scope
        org_id: Optional for org scope (defaults to 1)
        limit: Max vectors (100-20000)
        open_browser: Whether to auto-open TensorBoard

    Returns:
        Response data with viz_id and tensorboard_url
    """
    print(f"\n🎨 Generating {scope} visualization...")

    payload = {
        "scope": scope,
        "limit": limit
    }

    if search_query:
        payload["search_query"] = search_query
        print(f"   🔍 Search: {search_query}")

    if scope == "team":
        if not team_id:
            print("❌ Error: team_id required for team scope")
            sys.exit(1)
        payload["team_id"] = team_id
        print(f"   👥 Team ID: {team_id}")

    if scope == "org" and org_id:
        payload["org_id"] = org_id
        print(f"   🏢 Org ID: {org_id}")

    url = f"{API_BASE_URL}/api/v1/projector/generate"
    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()

    print(f"\n✅ Visualization generated!")
    print(f"   Viz ID:       {data['viz_id']}")
    print(f"   Collection:   {data['collection_name']}")
    print(f"   Status:       {data['status']}")
    print(f"   Vectors:      {data.get('num_points', '?'):,}")
    print(f"   Dimensions:   {data.get('vector_dimension', '?')}")
    print(f"   URL:          {data['tensorboard_url']}")
    print(f"\n   {data['message']}")

    if open_browser:
        print("\n🌐 Opening TensorBoard in browser...")
        webbrowser.open(data['tensorboard_url'])

    return data


def main():
    """Main test workflow."""
    print("=" * 60)
    print("🎨 TensorBoard Projector Test")
    print("=" * 60)

    # 1. Load stats
    try:
        stats = load_stats()
    except Exception as e:
        print(f"❌ Failed to load stats: {e}")
        sys.exit(1)

    # 2. Generate user visualization
    print("\n" + "=" * 60)
    try:
        viz = generate_visualization(
            scope="user",
            search_query=None,  # Change this to test search
            limit=5000,
            open_browser=True
        )
    except Exception as e:
        print(f"❌ Failed to generate visualization: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)
    print("\nNote: Wait 30-60 seconds for visualization to appear in TensorBoard.")


if __name__ == "__main__":
    main()
