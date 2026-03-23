SLACK_BASE = "https://hackclub.enterprise.slack.com"

EXTERNAL_CHANNELS = [
    {"slug": "hq", "label": "hq", "url": "https://hackclub.enterprise.slack.com/archives/C0C78SG9L"},
    {"slug": "2026-summer-interns", "label": "2026-summer-interns", "url": "https://hackclub.enterprise.slack.com/archives/C0ALD8SCMGD"},
    {"slug": "lounge", "label": "lounge", "url": "https://hackclub.enterprise.slack.com/archives/C0266FRGV"},
    {"slug": "flavortown", "label": "flavortown", "url": "https://hackclub.enterprise.slack.com/archives/C09MPB8NE8H"},
    {"slug": "hcb", "label": "hcb", "url": "https://hackclub.enterprise.slack.com/archives/CN523HLKW"},
    {"slug": "meta", "label": "meta", "url": "https://hackclub.enterprise.slack.com/archives/C0188CY57PZ"},
    {"slug": "out-of-context", "label": "out-of-context", "url": "https://hackclub.enterprise.slack.com/archives/C01270P3XFV"},
]

NETWORK_FIRST_QUESTION_OPTIONS = [
    {"question": "No? What's that?", "reply": "It's a new YSWS that Hack Club's hosting. You build apps that help you network and you earn grants for it."},
    {"question": "Yes! I've heard of it", "reply": "Nice! So you know about the $5 an hour grants for networking projects. Have you thought about what you'd build?"},
    {"question": "Maybe, what is it?", "reply": "YSWS stands for You Ship, We Ship. You ship networking projects and you can get grants for equipment or hosting credit."},
    {"question": "Tell me more", "reply": "You get $5 an hour in grants to spend on networking equipment or anything that helps you network, like hosting credit."},
]

NETWORK_FOLLOWUP_REPLIES = [
    {"reply": "You get $5 an hour in grants to spend on networking equipment or anything that helps you network, like hosting credit.", "questions": ["Tell me more about the grants"]},
    {"reply": "Just ship a networking project. Things like a chat app, a social thing, or anything that helps you connect with people.", "questions": ["What do I have to build?"]},
    {"reply": "Click the submit link in the header and fill out the form. If you have questions, drop them in the Slack.", "questions": ["How do I submit?"]},
    {"reply": "Hasn't launched yet but you can RSVP!", "questions": ["How do I apply?"]},
    {"reply": "Anything that helps you connect with people. Social media, chat apps, forums, or anything else that's about networking.", "questions": ["What counts as a project?"]},
    {"reply": "Still to be decided. Keep an eye on #network-announcements for updates.", "questions": ["When's the deadline?"]},
    {"reply": "Yes. Track time separately and make it clear in your readme.", "questions": ["Can I work with a team?"]},
    {"reply": "The Slack community is really helpful. Ask there anytime.", "questions": ["Where do I get help?"]},
    {"reply": "YSWS means You Ship, We Ship. You code projects and get cool prizes. For Network we focus on projects that help you connect with others.", "questions": ["What's YSWS?"]},
    {"reply": "We think so too! Pick a project idea, ship it, then submit and join the community on Slack.", "questions": ["That's really cool!"]},
]

NETWORK_FAQ_EXISTING = [
    {"from": "musty", "message": "How do I apply for Network?"},
    {"from": "Heidi", "message": "Fill out the form linked at the top of this channel. Describe your project and how it helps you network."},
    {"from": "Kenta", "message": "What counts as a networking project?"},
    {"from": "Heidi", "message": "Anything that helps you connect with others. Chat apps, social tools, forums, or even a personal site that gets you talking to people."},
    {"from": "biosphere", "message": "When's the deadline?"},
    {"from": "Heidi", "message": "Check the latest announcements in #network-announcements for dates. We usually run in waves."},
]

NETWORK_FAQ_QUESTIONS = [
    {"question": "How do I apply?", "reply": "Use the submit form linked in the header. Describe your project and how it helps you network."},
    {"question": "What counts as a networking project?", "reply": "Anything that helps you connect with people. Social media, chat apps, forums, or anything else that's about networking."},
    {"question": "When's the deadline?", "reply": "Still to be decided. Keep an eye on #network-announcements for updates."},
    {"question": "Can I work with a team?", "reply": "Yes. Track time separately and make it clear in your readme."},
    {"question": "Where do I get help?", "reply": "The Slack community is really helpful. Ask there anytime."},
]

NETWORK_ANNOUNCEMENTS = [
    {"from": "nullskulls", "message": "Welcome to Network! This is the YSWS where you ship networking related projects and earn grants to help you network. Check #network to learn more.", "timestamp": "Mar 14, 2026"},
]

HARDCODED_DMS = {
    "nullskulls": [
        {"from": "nullskulls", "message": "Hey! Excited to see what you submit!!!"},
        {"from": "You", "message": "Yeah, Thanks!"},
        {"from": "You", "message": "Quick question though, What counts as a valid project?"},
        {"from": "nullskulls", "message": "Anything networking related! By that I mean social media platforms, chat apps, neural networks and anything networking related!"},
        {"from": "You", "message": "Okay perfect!"},
    ],
    "dhamari": [
        {"from": "dhamari", "message": "I want the review queue down to 35 projects!"},
        {"from": "You", "message": "no"},
    ],
    "mustafa": [
        {"from": "mustafa", "message": "I'm a cat."},
        {"from": "You", "message": "???"},  
        {"from": "mustafa", "message": ":3"},
    ],
    "neon": [
        {"from": "neon", "message": "meow meow meow, communicate with people! mrrp mrrp"},
        {"from": "neon", "message": "bark bark"},
        {"from": "neon", "message": "woof owo"},
        {"from": "neon", "message": "fowoof"},
        {"from": "neon", "message": "meow"},
        {"from": "neon", "message": "uwu"},
        {"from": "You", "message": "yall are strange..."},
    ],
    "fireentity": [
        {"from": "You", "message": "Over the past two months, records show that you’ve only completed 6 or 7 reviews for Flavourtown. Being on the shipwright team is a privilege, not something you take lightly."},
        {"from": "fireentity", "message": "AAAAHAHAAHAHA SIX SEVEN"}
    ],
    "jay": [
        {"from": "jay", "message": "goo goo ga ga"},
        {"from": "You", "message": "jay dont"},
    ],
    "kuzu": [
        {"from": "kuzu", "message": "I just have one question for you, ARE YOU READY?"},
        {"from": "You", "message": "Ready for what?"},
        {"from": "kuzu", "message": "ARE YOU READY FOR THIS SUNDAY NIGHT WHEN WWE CHAMP JOHN CENA DEFENDS HIS TITLE"},
        {"from": "kuzu", "message": "IN THE WWE SUUUPERSLAMMMM"},
        {"from": "You", "message": "???"},
    ]
}

HARDCODED_DM_NAMES = {
    "nullskulls": "nullskulls",
    "dhamari": "dhamari",
    "mustafa": "mustafa",
    "neon": "neon",
    "fireentity": "fireentity",
    "jay": "jay",
    "kuzu": "kuzu",
}

AVATARS = {
    "Orpheus": None,
    "Heidi": None,
    "nullskulls": "img/nullskulls.png",
    "dhamari": "img/dhamari.png",
    "mustafa": "img/mustafa.png",
    "neon": "img/neon.png",
    "fireentity": "img/fireentity.png",
    "jay": "img/jay.png",
    "kuzu": "img/kuzu.png",
}
