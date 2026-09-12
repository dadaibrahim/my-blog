---
title: 'How I Built This Blog to (Mostly) Run Itself'
description: 'A dev-log on setting up an Astro blog, a Git-based deploy pipeline, and the automation stack behind it.'
pubDate: 'Sep 12 2026'
heroImage: '../../assets/blog-placeholder-1.jpg'
---

I wanted to start writing about code, automation, and AI — but I didn't want "maintaining the blog" to become its own part-time job. So instead of picking a CMS and logging in every time I wanted to publish, I set this up as a static site with a pipeline behind it: write a file, push it, and it's live.

## The stack

- **Astro** for the site itself — it ships almost no JavaScript by default, which matters for both load speed and SEO.
- **GitHub** as the source of truth. Every post is a Markdown file in a repo.
- **Render** for hosting, connected directly to the repo. Push to `main`, and it rebuilds and redeploys automatically — no manual "publish" button anywhere.

That's the whole publishing model: a commit *is* a publish.

## Why static + Git instead of a traditional CMS

A hosted CMS gets you writing faster on day one, but it puts a web app between me and my content. With a static site:

- Every post has real version history, because it's just Git.
- There's no server to patch, no database to back up, no login page to secure.
- The hosting is free and scales without me thinking about it.
- It's automation-friendly by design — a workflow that can write a file and run `git push` can publish a post. No API calls to a CMS required.

That last point is the real reason I went this route. The plan isn't just to blog — it's to build a pipeline that handles research, drafting, and distribution, with me reviewing and steering rather than doing every step by hand.

## What's next

Right now this is just the skeleton: the site is live, the deploy pipeline works, and this post is proof both actually function end to end. From here, the plan is to wire up automation on top — pulling in topic ideas, drafting with AI, and pushing distribution out to social — while I stay in the loop on quality and direction.

If you're building something similar, the short version is: get the boring infrastructure working and boring *first*. Everything you automate on top of a flaky foundation just breaks in more places.
