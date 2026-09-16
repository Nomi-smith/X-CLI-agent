#!/usr/bin/env python3
"""
xcli - a command-line tool for interacting with X (Twitter) via the X API v2.

Setup
-----
1. Create a developer account + App at https://developer.x.com
   (you'll need OAuth 1.0a User Context keys with Read+Write permission
   for anything that posts/likes/retweets, and a Bearer Token for
   read-only calls like search and timelines).
2. Store credentials either as environment variables:
       X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, X_BEARER_TOKEN
   or interactively:
       python3 xcli.py configure

Usage
-----
    python3 xcli.py whoami
    python3 xcli.py post "Hello world"
    python3 xcli.py post "Replying!" --reply-to 1234567890
    python3 xcli.py thread thread.txt
    python3 xcli.py delete 1234567890
    python3 xcli.py timeline --user someuser --count 10
    python3 xcli.py search "climate change" --count 20
    python3 xcli.py user someuser
    python3 xcli.py like 1234567890
    python3 xcli.py unlike 1234567890
    python3 xcli.py retweet 1234567890
    python3 xcli.py unretweet 1234567890

See README.md for details, including current X API pricing.
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import tweepy
except ImportError:
    print("Missing dependency. Install with: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

CONFIG_DIR = Path.home() / ".config" / "xcli"
CONFIG_FILE = CONFIG_DIR / "credentials.json"

ENV_KEYS = {
    "api_key": "X_API_KEY",
    "api_secret": "X_API_SECRET",
    "access_token": "X_ACCESS_TOKEN",
    "access_token_secret": "X_ACCESS_TOKEN_SECRET",
    "bearer_token": "X_BEARER_TOKEN",
}


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

def load_credentials():
    creds = {}
    if CONFIG_FILE.exists():
        try:
            creds.update(json.loads(CONFIG_FILE.read_text()))
        except json.JSONDecodeError:
            pass
    # Environment variables take priority over the saved config file.
    for key, env_name in ENV_KEYS.items():
        val = os.environ.get(env_name)
        if val:
            creds[key] = val
    return creds


def save_credentials(creds):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(creds, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)  # no-op on Windows, harmless
    except OSError:
        pass


def get_client(require_write=False):
    creds = load_credentials()
    bearer = creds.get("bearer_token")
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    access_token = creds.get("access_token")
    access_token_secret = creds.get("access_token_secret")
    has_oauth1 = all([api_key, api_secret, access_token, access_token_secret])

    if require_write and not has_oauth1:
        sys.exit(
            "This action needs write access (posting/liking/retweeting).\n"
            "Run `python3 xcli.py configure` or set X_API_KEY, X_API_SECRET,\n"
            "X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET (OAuth 1.0a, Read+Write app)."
        )
    if not require_write and not bearer and not has_oauth1:
        sys.exit(
            "No credentials found.\n"
            "Run `python3 xcli.py configure` or set X_BEARER_TOKEN (read-only)\n"
            "or the full OAuth 1.0a credential set."
        )

    return tweepy.Client(
        bearer_token=bearer,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )


def cmd_configure(args):
    print(f"Enter your X API credentials (saved to {CONFIG_FILE}, blank = skip/keep).")
    creds = load_credentials()
    for key, label in [
        ("api_key", "API Key"),
        ("api_secret", "API Key Secret"),
        ("access_token", "Access Token"),
        ("access_token_secret", "Access Token Secret"),
        ("bearer_token", "Bearer Token"),
    ]:
        current = " [already set]" if creds.get(key) else ""
        val = input(f"{label}{current}: ").strip()
        if val:
            creds[key] = val
    save_credentials(creds)
    print(f"Saved to {CONFIG_FILE} (permissions restricted to your user).")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_whoami(args):
    client = get_client(require_write=False)
    me = client.get_me(user_fields=["public_metrics", "description"])
    u = me.data
    print(f"@{u.username} ({u.name})  ID: {u.id}")
    if u.description:
        print(f"Bio: {u.description}")
    if u.public_metrics:
        m = u.public_metrics
        print(f"Followers: {m['followers_count']} | Following: {m['following_count']} | Posts: {m['tweet_count']}")


def cmd_post(args):
    client = get_client(require_write=True)
    kwargs = {"text": args.text}
    if args.reply_to:
        kwargs["in_reply_to_tweet_id"] = args.reply_to
    resp = client.create_tweet(**kwargs)
    tweet_id = resp.data["id"]
    print(f"Posted: https://x.com/i/web/status/{tweet_id}")


def split_thread_file(raw):
    """Split thread file text on lines containing only '---'."""
    parts = [p.strip() for p in raw.strip().split("\n---\n")]
    return [p for p in parts if p]


def cmd_thread(args):
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"File not found: {path}")
    parts = split_thread_file(path.read_text())
    if not parts:
        sys.exit("No post text found (separate posts with a line containing only ---).")

    client = get_client(require_write=True)
    prev_id = None
    for i, text in enumerate(parts, 1):
        kwargs = {"text": text}
        if prev_id:
            kwargs["in_reply_to_tweet_id"] = prev_id
        resp = client.create_tweet(**kwargs)
        prev_id = resp.data["id"]
        print(f"[{i}/{len(parts)}] Posted: https://x.com/i/web/status/{prev_id}")


def cmd_delete(args):
    client = get_client(require_write=True)
    client.delete_tweet(args.tweet_id)
    print(f"Deleted post {args.tweet_id}")


def _print_tweets(tweets):
    for t in tweets:
        m = t.public_metrics or {}
        print(f"[{t.created_at}] {t.text}")
        print(f"  <3 {m.get('like_count', 0)}  RT {m.get('retweet_count', 0)}  ID: {t.id}\n")


def cmd_timeline(args):
    client = get_client(require_write=False)
    user = client.get_user(username=args.user)
    if not user.data:
        sys.exit(f"User not found: {args.user}")
    resp = client.get_users_tweets(
        user.data.id,
        max_results=min(max(args.count, 5), 100),
        tweet_fields=["created_at", "public_metrics"],
    )
    if not resp.data:
        print("No posts found.")
        return
    _print_tweets(resp.data)


def cmd_search(args):
    client = get_client(require_write=False)
    resp = client.search_recent_tweets(
        query=args.query,
        max_results=min(max(args.count, 10), 100),
        tweet_fields=["created_at", "public_metrics"],
    )
    if not resp.data:
        print("No results.")
        return
    _print_tweets(resp.data)


def cmd_user(args):
    client = get_client(require_write=False)
    resp = client.get_user(
        username=args.username,
        user_fields=["public_metrics", "description", "location"],
    )
    if not resp.data:
        sys.exit(f"User not found: {args.username}")
    u = resp.data
    print(f"@{u.username} ({u.name})")
    if u.description:
        print(f"Bio: {u.description}")
    if u.location:
        print(f"Location: {u.location}")
    if u.public_metrics:
        m = u.public_metrics
        print(f"Followers: {m['followers_count']} | Following: {m['following_count']} | Posts: {m['tweet_count']}")


def cmd_like(args):
    client = get_client(require_write=True)
    client.like(args.tweet_id)
    print(f"Liked {args.tweet_id}")


def cmd_unlike(args):
    client = get_client(require_write=True)
    client.unlike(args.tweet_id)
    print(f"Unliked {args.tweet_id}")


def cmd_retweet(args):
    client = get_client(require_write=True)
    client.retweet(args.tweet_id)
    print(f"Retweeted {args.tweet_id}")


def cmd_unretweet(args):
    client = get_client(require_write=True)
    client.unretweet(args.tweet_id)
    print(f"Un-retweeted {args.tweet_id}")


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="xcli", description="Interact with X (Twitter) from the command line.")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("configure", help="Set up API credentials")
    sp.set_defaults(func=cmd_configure)

    sp = sub.add_parser("whoami", help="Show the authenticated account")
    sp.set_defaults(func=cmd_whoami)

    sp = sub.add_parser("post", help="Post to X")
    sp.add_argument("text")
    sp.add_argument("--reply-to", dest="reply_to", default=None, help="Post ID to reply to")
    sp.set_defaults(func=cmd_post)

    sp = sub.add_parser("thread", help="Post a thread from a text file (posts separated by a line of ---)")
    sp.add_argument("file")
    sp.set_defaults(func=cmd_thread)

    sp = sub.add_parser("delete", help="Delete a post")
    sp.add_argument("tweet_id")
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("timeline", help="Show a user's recent posts")
    sp.add_argument("--user", required=True)
    sp.add_argument("--count", type=int, default=10)
    sp.set_defaults(func=cmd_timeline)

    sp = sub.add_parser("search", help="Search recent posts")
    sp.add_argument("query")
    sp.add_argument("--count", type=int, default=10)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("user", help="Look up a user profile")
    sp.add_argument("username")
    sp.set_defaults(func=cmd_user)

    sp = sub.add_parser("like", help="Like a post")
    sp.add_argument("tweet_id")
    sp.set_defaults(func=cmd_like)

    sp = sub.add_parser("unlike", help="Remove a like")
    sp.add_argument("tweet_id")
    sp.set_defaults(func=cmd_unlike)

    sp = sub.add_parser("retweet", help="Repost (retweet) a post")
    sp.add_argument("tweet_id")
    sp.set_defaults(func=cmd_retweet)

    sp = sub.add_parser("unretweet", help="Undo a repost")
    sp.add_argument("tweet_id")
    sp.set_defaults(func=cmd_unretweet)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except tweepy.errors.Unauthorized as e:
        sys.exit(f"Unauthorized (401): check your credentials. {e}")
    except tweepy.errors.Forbidden as e:
        sys.exit(f"Forbidden (403): your API access/credits may not cover this endpoint. {e}")
    except tweepy.errors.TooManyRequests as e:
        sys.exit(f"Rate limited (429): try again shortly. {e}")
    except tweepy.TweepyException as e:
        sys.exit(f"X API error: {e}")


if __name__ == "__main__":
    main()
