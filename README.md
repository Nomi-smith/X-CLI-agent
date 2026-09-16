# xcli

A command-line tool for interacting with X (Twitter) — post, delete, read
timelines, search, look up users, like, and retweet — built on the X API v2
via [tweepy](https://www.tweepy.org/).

## 1. Get API credentials

1. Go to **developer.x.com** and create a Project + App (sign-in with your X account).
2. Under the app's **User authentication settings**, turn on OAuth 1.0a with
   **Read and Write** permissions — this is required for anything that
   posts, deletes, likes, or retweets.
3. Generate:
   - **API Key** and **API Key Secret**
   - **Access Token** and **Access Token Secret** (make sure these are
     regenerated *after* you set Read+Write, or they'll be read-only)
   - **Bearer Token** (optional — only needed if you want read-only access
     without the full OAuth 1.0a set)

### A note on cost

X ended free API access for new developers in February 2026 — there's no
longer a free tier to sign up for. Access is now pay‑per‑use by default:
roughly **$0.015 per post you create** (about $0.20 if it contains a link)
and **$0.005 per post you read**, paid for with credits you buy in the
developer portal; reads are capped at 2,000,000/month before you'd need an
Enterprise plan. Legacy fixed-price Basic ($200/mo) and Pro ($5,000/mo)
plans still work if you already had one, but are closed to new signups.

For light personal use of this CLI (checking your account, posting
occasionally, the odd search), this comes out to a few dollars a month —
but pricing has shifted more than once in 2026, so treat the numbers above
as a ballpark and confirm current rates on the pricing page in your
developer portal before you rely on them.

## 2. Install

```bash
pip install -r requirements.txt
```

## 3. Configure credentials

Either set environment variables:

```bash
export X_API_KEY=...
export X_API_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...
export X_BEARER_TOKEN=...       # optional, read-only calls only
```

or run the interactive setup, which saves them to
`~/.config/xcli/credentials.json` (file permissions restricted to your user):

```bash
python3 xcli.py configure
```

Environment variables always take priority over the saved file, so you can
override per-shell without touching the config.

## 4. Usage

```bash
python3 xcli.py whoami                              # your authenticated account
python3 xcli.py post "Hello world"                   # post
python3 xcli.py post "Replying!" --reply-to 1234567890
python3 xcli.py thread thread.txt                    # post a thread, see below
python3 xcli.py delete 1234567890
python3 xcli.py timeline --user someuser --count 10
python3 xcli.py search "climate change" --count 20
python3 xcli.py user someuser                        # look up a profile
python3 xcli.py like 1234567890
python3 xcli.py unlike 1234567890
python3 xcli.py retweet 1234567890
python3 xcli.py unretweet 1234567890
```

### Posting a thread

Put each post's text in `thread.txt`, separated by a line containing only
`---`:

```
First post in the thread.
---
Second post, posted as a reply to the first.
---
Third and last.
```

## Notes

- `search` uses `search_recent_tweets`, which only covers roughly the last
  7 days of posts — that's an X API limitation, not this tool's.
- A `403 Forbidden` error usually means your credential set doesn't have
  the right permission (e.g. Bearer Token trying to post) or your account
  is out of credits — check the developer portal.
- Don't commit `~/.config/xcli/credentials.json` or your env vars to git.
