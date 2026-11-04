# Contra case study draft — MarketPulse

## Project setup

- **Title:** MarketPulse — Market intelligence, in focus
- **Type:** Self-initiated product concept and MVP
- **Role:** Product design and full-stack development
- **Tools:** Python, FastAPI, SQLAlchemy, PostgreSQL, BeautifulSoup, Playwright, Docker, HTML, CSS, JavaScript
- **Suggested skills:** Product design, full-stack development, API development, data normalization, web scraping
- **Thumbnail line:** A calmer way to track prices, availability, and competitors.

## Short project description

MarketPulse is a market-monitoring MVP that collects public listings, normalizes product data, and surfaces changes in one focused workspace.

## Overview

Market research often starts with a growing collection of store tabs, spreadsheets, and one-off checks. I designed and built MarketPulse as a single workspace for organizing monitored sources and reviewing listing changes over time.

This is an independent concept project. Sample values in the portfolio preview are illustrative; they are not collected market results.

## The challenge

Create a usable path from a source URL to a normalized listing and a recorded change, while keeping projects, source health, and market movement easy to scan.

## The approach

I separated the product into three parts: a workspace dashboard for scanning activity, configurable source definitions for describing how listings are found, and a backend pipeline for turning scraped records into consistent snapshots and change events.

The scraper supports static HTML, JavaScript-rendered HTML, and JSON APIs. A normalization layer standardizes common fields and deduplicates records. Successful runs update current snapshots, append history, and record price, availability, title, description, and listing-presence changes. Empty or invalid runs fail safely instead of marking the whole source as removed.

## The solution

- Workspace-based projects organize research by category.
- Sources define a URL, scraper type, and CSS or JSON field mappings.
- A manual run fetches, validates, normalizes, and deduplicates listings.
- Snapshots show the latest state; append-only history keeps observations over time.
- A change feed records price and availability movement, new listings, removals, and content changes.
- The dashboard preview makes the product legible before a workspace has live data. Its sample data is clearly labeled.

## Built with

FastAPI and SQLAlchemy power the API and relational data model. The pipeline uses Requests, BeautifulSoup, and Playwright. The interface is responsive HTML, CSS, and JavaScript, with Docker Compose for local orchestration.

## Current scope

This project is an MVP, not a production deployment. Scrapes are started manually and run as in-process background tasks. Durable queueing, scheduled runs, report generation, and alert delivery are not implemented yet. The portfolio preview chart is illustrative; a historical chart API is future work.

## Visuals to upload

Contra's current case-study guide recommends beginning with images or video and suggests 1600 × 1200 visuals. Capture these from the running interface and upload them in this order:

1. **Cover:** dashboard overview with the “Sample workspace” label visible.
2. **Workflow:** project view showing a configured source and its manual run status.
3. **Data detail:** tracked listings and the price-change feed.

Do not crop away the sample-data label on the dashboard cover. Replace this draft's tool list or scope notes if the shipped build changes. [Contra case-study guide](https://help.contra.com/en/articles/9322393-how-to-build-a-case-study-from-scratch-on-contra)
