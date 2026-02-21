"""Spotify music control agent."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


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
    instructions: ClassVar[str] = (
        "You control Spotify playback via the Spotify Web API (OAuth2 authenticated).\n\n"
        "Available tools:\n"
        "- get_current_track: Get the currently playing track with artist and album info.\n"
        "- play_music: Resume playback or search and play a specific track by query.\n"
        "- pause_music: Pause the current playback.\n"
        "- skip_track: Skip to the next track.\n"
        "- previous_track: Go back to the previous track.\n"
        "- set_volume: Set playback volume (0-100).\n"
        "- search_tracks: Search for tracks matching a query, returns up to 5 results.\n\n"
        "Requires SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI "
        "environment variables."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def get_current_track(ctx: RunContext[object]) -> dict:
            """Get the currently playing Spotify track."""
            sp = ctx.deps
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

        @agent.tool
        def play_music(ctx: RunContext[object], query: str = "") -> dict:
            """Play music on Spotify, optionally searching for a track or artist."""
            sp = ctx.deps
            if query:
                results = sp.search(q=query, limit=1, type="track")
                tracks = results.get("tracks", {}).get("items", [])
                if tracks:
                    sp.start_playback(uris=[tracks[0]["uri"]])
                    return {"playing": True, "track": tracks[0]["name"]}
                return {"error": "Track not found"}
            sp.start_playback()
            return {"playing": True}

        @agent.tool
        def pause_music(ctx: RunContext[object]) -> dict:
            """Pause Spotify playback."""
            ctx.deps.pause_playback()
            return {"paused": True}

        @agent.tool
        def skip_track(ctx: RunContext[object]) -> dict:
            """Skip to the next track on Spotify."""
            ctx.deps.next_track()
            return {"skipped": True}

        @agent.tool
        def previous_track(ctx: RunContext[object]) -> dict:
            """Go back to the previous track on Spotify."""
            ctx.deps.previous_track()
            return {"previous": True}

        @agent.tool
        def set_volume(ctx: RunContext[object], volume: int) -> dict:
            """Set the Spotify playback volume (0-100)."""
            vol = max(0, min(100, volume))
            ctx.deps.volume(vol)
            return {"volume": vol}

        @agent.tool
        def search_tracks(ctx: RunContext[object], query: str, limit: int = 5) -> dict:
            """Search Spotify for tracks matching a query."""
            sp = ctx.deps
            results = sp.search(q=query, limit=limit, type="track")
            items = [
                {
                    "name": t["name"],
                    "artist": ", ".join(a["name"] for a in t["artists"]),
                    "uri": t["uri"],
                }
                for t in results.get("tracks", {}).get("items", [])
            ]
            return {"results": items}

        return agent

    def _build_client(self) -> Any:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        cache_path = os.environ.get("SPOTIFY_TOKEN_CACHE", ".spotify_cache")
        auth_manager = SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID", ""),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing",
            cache_path=cache_path,
            open_browser=False,
        )

        # Check if we have a cached token; if not, raise a clear error
        token_info = auth_manager.cache_handler.get_cached_token()
        if not token_info:
            auth_url = auth_manager.get_authorize_url()
            raise RuntimeError(
                f"Spotify authorization required. Visit this URL to authorize: {auth_url} "
                f"Then run: angie config spotify --callback-url '<redirect_url_with_code>'"
            )

        return spotipy.Spotify(auth_manager=auth_manager)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("SpotifyAgent executing")
        try:
            import spotipy  # noqa: F401 — verify installed

            sp = self._build_client()
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="what is currently playing?")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=sp)
            output = str(result.output)
            return {"status": "success", "summary": output, "result": output}
        except ImportError:
            return {
                "status": "error",
                "summary": "spotipy is not installed.",
                "error": "spotipy not installed",
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("SpotifyAgent error")
            return {"status": "error", "summary": f"Spotify error: {exc}", "error": str(exc)}
