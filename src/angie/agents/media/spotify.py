"""Spotify music control agent."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class SpotifyAgent(BaseAgent):
    name: ClassVar[str] = "SpotifyAgent"
    slug: ClassVar[str] = "spotify"
    description: ClassVar[str] = "Spotify music control."
    capabilities: ClassVar[list[str]] = [
        "spotify",
        "music",
        "play",
        "pause",
        "playlist",
        "song",
        "skip",
        "volume",
    ]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "current")
        self.logger.info("SpotifyAgent action=%s", action)
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=os.environ.get("SPOTIFY_CLIENT_ID", ""),
                    client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
                    redirect_uri=os.environ.get(
                        "SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"
                    ),
                    scope="user-read-playback-state user-modify-playback-state user-read-currently-playing",
                    cache_path=os.environ.get("SPOTIFY_TOKEN_CACHE", ".spotify_cache"),
                )
            )
            return self._dispatch(sp, action, task.get("input_data", {}))
        except ImportError:
            return {"error": "spotipy not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("SpotifyAgent error")
            return {"error": str(exc)}

    def _dispatch(self, sp: Any, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "current":
            track = sp.current_playback()
            if not track or not track.get("item"):
                return {"playing": False}
            item = track["item"]
            return {
                "playing": track["is_playing"],
                "track": item["name"],
                "artist": ", ".join(a["name"] for a in item["artists"]),
                "album": item["album"]["name"],
            }

        if action == "play":
            query = data.get("query", "")
            if query:
                results = sp.search(q=query, limit=1, type="track")
                tracks = results.get("tracks", {}).get("items", [])
                if tracks:
                    sp.start_playback(uris=[tracks[0]["uri"]])
                    return {"playing": True, "track": tracks[0]["name"]}
                return {"error": "Track not found"}
            sp.start_playback()
            return {"playing": True}

        if action == "pause":
            sp.pause_playback()
            return {"paused": True}

        if action == "skip":
            sp.next_track()
            return {"skipped": True}

        if action == "previous":
            sp.previous_track()
            return {"previous": True}

        if action == "volume":
            vol = int(data.get("volume", 50))
            sp.volume(vol)
            return {"volume": vol}

        if action == "search":
            query = data.get("query", "")
            results = sp.search(q=query, limit=5, type="track")
            items = [
                {
                    "name": t["name"],
                    "artist": ", ".join(a["name"] for a in t["artists"]),
                    "uri": t["uri"],
                }
                for t in results.get("tracks", {}).get("items", [])
            ]
            return {"results": items}

        return {"error": f"Unknown action: {action}"}
