# Slack App Developer Best Practices Guide

> Source: https://w.amazon.com/bin/view/AmazonUC/SIGNAL/OPUS/SlackApps/SlackAppBestPractices/
> Primary Owner: amazonuc (LDAP)
> Saved for local reference on 2026-03-21

## Contents

1. [General Do's and Don'ts](#general-dos-and-donts)
2. [Development Planning](#development-planning)
3. [User Experience Design](#user-experience-design)
4. [App Ownership and Operations](#app-ownership-and-operations)
5. [App Configuration](#app-configuration)
6. [Access Tokens and App Security](#access-tokens-and-app-security)
7. [App Distribution and Org Level Apps](#app-distribution)
8. [App Hosting](#app-hosting)
9. [Appendix](#appendix)

> **Have questions about getting your Slack App to production?** Check out: https://w.amazon.com/bin/view/AmazonUC/SIGNAL/OPUS/SlackApps/SlackAppFAQ

---

## General Do's and Don'ts

| Do's | Don'ts |
|------|--------|
| Own the app: feature enhancements, bug fixes, frequent feature audits, update collaborators, succession/hand off plan, CTI/Slack support channel, App Wiki, monitoring tools and dashboards | Don't abandon your App |
| Focus on user experience - app needs to be simple to use | Don't build a single app to solve many use cases |
| Make sure your App is accessibility and localization friendly | Do not use graphic animations. If possible, support multiple languages |
| Provide proper documentation and onboarding resources (App home, App 101 guide, support channel) | Don't leave the App without instructions or onboarding material - this will hurt App adoption |
| Consider scale, especially projected usage (e.g. future onboarding users) | Don't build the app with current usage in mind |
| Go to AppSec page (https://appsec.corp.amazon.com/) and review what is required. All Apps require AppSec review. | Don't submit the app for security review and leave the request hanging. Don't avoid looking at AppSec intake form prior to building. |
| Use Events API instead of RTM API | Don't use RTM API (see App Configuration section) |
| Post app questions in #slack-community-apps-help. Post sandbox questions in #slack-app-sandbox-support | Don't build/design the app with Admin APIs without prior approvals from Opus team/security partners |
| Follow Slack guidance on how to secure Slack apps | Don't expose your App URLs publicly |
| Store tokens and secrets in AWS Secrets Manager | Don't hard code or leave tokens/secrets open |
| Know data security guidelines: AWS Data Decision Making Guide (https://policy.amazon.com/guideline/42664). Get familiar with AWS Data Handling Tenets (https://policy.amazon.com/standard/42682) | Don't avoid or ignore data security guidance and guidelines |

---

## Development Planning

### Before building the App

- Clearly define the App purpose
- Understand the various use cases involved in the App
- Determine the App usage
- Is the App being developed for a particular team or being built as an add-on functionality to Slack?

### Check App Ledger or App list

- Check the [Amazon hosted App ledger](https://w.amazon.com/bin/view/AmazonUC/SIGNAL/OPUS/SlackApps/FirstPartyApps) for Apps already in production and development
- Check if any current apps cater to your App idea
- If no match, update the ledger and proceed with development
- If there is a match, work with the original App team to understand use case gaps
- Work with Opus team to get the existing app added to your respective workspace

---

## User Experience Design

### Plan with purpose

- Define the goal: consider how your app will help make people's working lives simpler, more pleasant, and/or more productive
- Plan ahead: Storyboard how each interaction will look
- Less is more: Keep text segments bite-sized and conversational

### Understand your audience

- Be mindful to cater to all ages, races, genders, and abilities
- Consider users on mobile and those with potentially poor internet connections
- Additional factors:
  - Time zones
  - Accessibility
  - Localization
  - Workspace size / Grid setup
  - User & Workspace preferences (retention, DND, etc.)

### Communicate with clarity

- The best Apps often have a personality of their own, mirroring the developer's "brand voice"
- Be brief, clear, AND empathetic
  - Less is often more
  - Avoid jargon
  - Use actionable words for buttons ("Place Order" instead of "Submit")

### Create a great onboarding experience

- Have an informative, concise welcome message in DM after installation
- Leverage the [App Home](https://api.slack.com/surfaces/tabs) tab to provide clear details on App functionality
- Offer an opt-in tutorial and "help" subcommand if you use Slash commands/Shortcuts

### Be a good citizen (app) inside Slack

- Ensure app notifications are considerate with appropriate:
  - Frequency
  - Detail
  - Calls to action
  - Audience (DM/MPDM/channel)
- Be mindful of Spam
- Ensure users are notified on interactions with Apps

### Consider Scale

- Apps are subject to rate limits, so consider expected usage during the design phase
- Apps installed in multiple workspaces or at the [organization level](https://api.slack.com/enterprise/apps) require a different design
- Refer to [Building apps in Enterprise Grid](https://api.slack.com/enterprise/grid#what_is_enterprise_grid) for an overview

---

## App Ownership and Operations

### Own the App

- Continue to own the app for performance updates and feature upgrades
- Set up frequent cadence to review app functionality and validity
- Set up a process to receive feedback and bug reports from end users
- Perform frequent audit on app scopes
- Audit collaborators/co-owners of the app
- Have a succession/hand off plan in case ownership changes (promoted, change teams, change orgs, change companies)
- Build monitoring and dashboards for app outages/alerts

### App Sec Review

- Submit the [App for AppSec review](https://appsec.corp.amazon.com/response_sets/new?intakeTemplate=Feature+Enhancement+-+Internal+Service) post development in sandbox
- Provide all necessary details in the template for successful approval
  - When findings are presented, make recommended changes and post back remediations in same ticket
  - If an app is rejected, it will likely require redesign or is out of scope for Slack at Amazon

---

## App Configuration

### Interactivity

- Transform your Slack app into a powerful workflow partner by making messages interactive
- Interactive components can be inserted into messages, converting them from simple information relays into powerful tools
- You can leverage [Socket Mode](https://api.slack.com/apis/connections/socket) which allows your app to use the Events API and Interactive components without exposing a public HTTP Request URL

### APIs

#### Examples and Tutorials
- See tutorials: https://api.slack.com/tutorials
- Blueprint examples: https://api.slack.com/best-practices/blueprints

#### Web API
- Suite of HTTP-based APIs spanning many use cases including methods for conversations/channels, messages, administration, and more
- Example: `chat.postMessage` to send a message as a bot or user
- Each web API method is rate limited according to a rate limit tier
- Every Web API method is restricted to one or more [OAuth Permission Scopes](https://api.slack.com/docs/oauth-scopes). Always use the principle of least privilege.
- Refer to [Slack API Methods](https://api.slack.com/methods) for more details

#### Events API
- Subscription-based (pub-sub) API which delivers payloads to the HTTP endpoint of your choice
- Example: Your server can receive message events when a message is posted to a channel your app is in
- Your app will be limited to 30k events per app/workspace, so plan accordingly
- Event subscriptions are restricted by [OAuth Permission Scopes](https://api.slack.com/docs/oauth-scopes). Always use the principle of least privilege.
- Refer to [API Events](https://api.slack.com/events) for a list of available events

#### RTM API (NOT RECOMMENDED)
- **Slack no longer recommends using the RTM API. Use the Events API instead.**
- RTM API is a legacy API; Slack's roadmap is to move to Events API
- No enhancements or new features planned for RTM API
- No process or resources in place to fix associated bugs

### API Rate Limit Strategies
- Slack APIs will tolerate a small amount of calls above documented rate limits (bursting)
- When designing Apps for your enterprise, do NOT rely on tolerance to handle unexpected traffic
- A throttled queue is a suitable strategy for ensuring multiple requests are executed in order and with tolerable frequency

### App Scopes
- Identify pre-approved scopes and restricted scopes
- Reference Slack API scopes: https://api.slack.com/scopes

---

## Access Tokens and App Security

Access tokens are the keys to the Slack platform. Tokens tie together all the scopes and permissions your app has obtained, allowing it to read, write, and interact.

See [Slack's API documentation on token types](https://api.slack.com/authentication/token-types) for more details.

### Important Note About Token Security

- Store access tokens and any secret in **AWS Secrets Manager**: https://www.aristotle.a2z.com/implementations/70
- Rotate access tokens every 90 days
  - Slack follows token rotation patterns based on the [OAuth 2.0 spec](https://datatracker.ietf.org/doc/html/rfc6749)
  - See [Slack API documentation on token rotation](https://api.slack.com/authentication/rotation)
  - Ensure you [implement OAuth 2.0](https://api.slack.com/authentication/rotation) on your app as it will be required to rotate tokens

### User Tokens
- Represent workspace members
- Issued for the user who installed the app and for users who authenticated the app
- Token strings begin with `xoxp-`
- Gain resource-based OAuth scopes requested in the installation process
- Represent the same access a user has to a workspace (channels, conversations, users, reactions, etc.)
- Write actions are performed as if by the user themselves

### Bot Tokens
- Represent a bot associated with the app installed in a workspace
- Not tied to a user's identity; tied to your app
- Stay installed even when an installing user is deactivated (usually the best choice)
- Token strings begin with `xoxb-`
- Can request individual scopes, similar to user tokens

### App-level Tokens
- Represent your app across organizations
- Include installations by all individual users on all workspaces in a given organization

### Verifying Requests from Slack

#### Signing Secrets
- Slack signs its requests using a secret unique to your app
- Process:
  1. Your app receives a request from Slack
  2. Your app computes a signature based on the request
  3. You verify the computed signature matches the signature on the request
- More details: https://api.slack.com/authentication/verifying-requests-from-slack#about

#### Mutual TLS
- Requests from Slack also support authentication through Mutual TLS
- Differs from request signing in where and how it occurs
- You configure your TLS-terminating server to authenticate client certificates from Slack
- More details: https://api.slack.com/authentication/verifying-requests-from-slack

### App Compliance
- The App should be ready to support any legal and compliance requests raised by policy team

---

## App Distribution

Ask yourself: Where should my Slack app live? Three options:

### Single-workspace apps
- Apps start life residing in one workspace
- Suitable for internal tools for your team
- Does not require implementing the OAuth 2.0 flow
- You can generate bot and/or user tokens directly from the app configuration (Install App page) without writing OAuth code

### Distributed apps (Multi-workspace)

Before activating public distribution:
- Your application must handle the **OAuth 2.0 installation flow** (exchanging a code for a token and storing installation metadata in AWS Secrets Manager)
- **Enable SSL across the board**: All URLs (OAuth 2.0 Redirect, Events API Request, Interactivity, Options Load, Slash Command URLs) must use HTTPS

### Org-level apps
- An [Org-level app](https://api.slack.com/enterprise/apps) can be installed once at the organization level and be available across many workspaces in the Slack Grid
- Opus team prefers this for any app with utility for Amazonians outside your workspace
- Simplifies token management (one set of tokens for the entire org)

#### How to enable org-level:
1. Go to your [app config](https://api.slack.com/apps)
2. Find the **Org Level Apps** section in the sidebar
3. Press the **Opt-in** button

Migration guide: https://api.slack.com/enterprise/apps/migration

#### Benefits for Slack users:
- Enterprise Org administrators can add an app easily across all workspaces
- Pre-approved apps can be auto-installed when a workspace is created

#### Benefits for your app:
- Easily installed for an entire organization
- Simplifies token management
- Makes supporting Enterprise Grid simpler

---

## App Hosting

There are numerous considerations when defining infrastructure for your Slack App. It is up to the developer to construct the appropriate infrastructure. 

Reference: [Slack Event Notification Construct CDK](https://code.amazon.com/packages/SlackEventNotificationConstructCDK/trees/mainline)

---

## Appendix

- [Amazon's Guide to get your App into Production](https://w.amazon.com/bin/view/AmazonUC/SIGNAL/OPUS/SlackApps/SlackAppFAQ)
- [Introduction to Slack Platform](https://api.slack.com/start/overview)
- [Building Slack applications](https://api.slack.com/start/building)
- [Slack developer blog](https://medium.com/slack-developer-blog)
- [Slack App repository](https://github.com/slackapi)
- [Sample slack apps](https://api.slack.com/tutorials/tags/slack-apps)
- [Guide to launch Slack Apps at Amazon](https://w.amazon.com/bin/view/AmazonUC/SIGNAL/OPUS/SlackApps/SlackAppFAQ)
