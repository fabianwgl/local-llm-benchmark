Weekly engineering sync
Date: Tuesday 16 September 2025, 10:00 to 10:50
Attendees: Marta Nowak (engineering manager), Marek Kowal (backend), Priya Raman (frontend), Jonas Weber (SRE), Aiko Tanaka (product), Dele Adeyemi (QA)
Transcript generated automatically from the call recording. Speaker names were added by hand.

Marta: Okay, it's two past, let's go. Can everyone hear me? Jonas, you're a robot again.

Jonas: Hang on. Better?

Marta: Better. So, agenda. The 4.2 release, the checkout rollout, API v1, the on-call thing I mentioned in chat, and Dele wanted five minutes on the end-to-end tests. Anything else?

Priya: I have a small one about browser support. It can go at the end.

Marta: Fine. Aiko, 4.2. You wanted to talk dates.

Aiko: Yes. So marketing has the newsletter going out on Friday, and they'd really like to mention the saved carts feature, which is in 4.2. If we ship Thursday they can say "it's live", which reads a lot better than "coming soon". So my ask is Thursday.

Marta: Thursday this week. The eighteenth.

Aiko: The eighteenth, yes.

Marta: Dele, where's the regression run?

Dele: The full suite kicks off tonight. With the new device farm it takes about a day, so I'd have results Wednesday night. If nothing serious comes up, Thursday is doable. If something serious comes up, it obviously isn't.

Marek: Backend is code complete. The only thing left on my side is the changelog.

Priya: Frontend's done too. There's one visual glitch on the cart drawer in landscape on small phones, but I wouldn't hold a release for it.

Marta: Okay. Then let's say Thursday. 4.2 goes out Thursday the eighteenth, assuming Dele's run is clean. Aiko, you can tell marketing it's likely but not promised.

Aiko: Great. I'll take "likely".

Marta: Next, the checkout rollout. This is the new checkout flow behind the flag. Aiko, what are you proposing?

Aiko: I'd like to go to fifty percent of users next week. We've had it on for staff for a month, nothing has exploded, and the conversion numbers from the internal test are good. Fifty percent gives us a real A/B comparison in one week instead of four.

Jonas: Fifty is a lot for a first step.

Aiko: Why? It works.

Jonas: It works for forty staff accounts. The new flow makes two extra calls to the payment provider per checkout, the address validation and the pre-authorisation. We have a rate limit with them. At fifty percent, on a Friday evening peak, I'm not confident we stay under it. And if we hit it, it's not only the new checkout that fails, the old one shares the same quota.

Marek: He's right about the quota. I looked last week. At full traffic the new flow would use about a hundred and thirty percent of what we're allowed. At fifty percent you're at maybe eighty, eighty-five, on a normal day. On a peak day I wouldn't want to bet on it.

Aiko: Can we get the limit raised?

Marek: I've asked. They said it takes two to three weeks and they want a traffic forecast from us first.

Aiko: Okay. So what number are you comfortable with?

Jonas: Ten.

Aiko: Ten is going to take forever to get significance.

Priya: It's not forever. With our volume, ten percent for a week gives you something like eleven thousand checkouts in the new flow. That's enough to see if conversion is in the same ballpark, which is all you need for the first step.

Aiko: Mm. Okay. Ten percent for a week, and then we look at the numbers and at the quota and decide the next step. I can live with that.

Marta: So that's decided: ten percent for one week, then review. Not fifty. When does it start?

Aiko: Whenever 4.2 is out, the flag control ships with it. So the week after the release.

Jonas: One thing we need for that. Right now the flag is on or off, per account. There's no percentage. Someone has to build the percentage control in the admin panel, otherwise "ten percent" means me running a script against the database, and I'd rather not.

Marta: Marek, can you take that? You wrote the flag service.

Marek: Sure. It's not a lot of work, the service already supports buckets, it just isn't exposed. I can have it by Monday.

Marta: Monday the twenty-second. Okay.

Priya: And while he's in there he can add dark mode to the admin panel. I've been asking for two years.

Marek: Absolutely. Dark mode by Friday, and I'll throw in world peace by Monday.

Jonas: Put it in the notes. "Marek: world peace, due Monday."

Marta: Please don't put it in the notes. Okay. API v1. Marek, this is yours as well, sorry.

Marek: That's fine. So, v1. We've been saying we'd turn it off for a year and a half. I pulled the numbers. In the last thirty days, three customers still called it. Three. One of them is Hartmann Logistik, which is about ninety percent of the v1 traffic, and the other two look like forgotten cron jobs. Everything v1 does, v2 does. Keeping v1 alive costs us a separate auth path and a whole set of tests that Dele's team has to keep green.

Dele: Forty-one tests, to be exact. I counted, out of spite.

Aiko: What do we owe those customers contractually?

Marek: Sixty days' notice. It's in the terms.

Aiko: So if we tell them by the end of September, we could switch it off at the start of December.

Marta: Is there any reason not to?

Jonas: From my side, the sooner the better. Half of the weird alerts at night are v1 timeouts.

Aiko: I want Hartmann handled with care. They're a big account. But a date is fine. First of December?

Marta: First of December 2025 is a Monday. Any objection? No? Then v1 is switched off on the first of December. That means the notice has to go out before the end of this month. Who writes it?

Aiko: I can send it, it should come from product. But I can't write the technical part, the migration guide, which endpoints map to which.

Marek: I'll write the draft. I know where the bodies are buried. Give me until next Thursday.

Aiko: This Thursday? The eighteenth?

Marek: No, no. Next week's Thursday, the twenty-fifth. This week I've got the changelog and I'm on call.

Aiko: The twenty-fifth works. That still leaves me a few days to get it through support and send it before the thirtieth.

Marta: Hold on, Marek. If you're on call this week, and you have the changelog, and now the deprecation draft, are you really also building the percentage control by Monday?

Marek: Hm. Honestly, no. One of them slips.

Marta: The notice has a contractual clock on it, so that one stays with you. Can somebody else take the admin panel piece?

Priya: I can take it. The admin panel is mostly my code anyway, I just need Marek to show me the bucket API. Ten minutes.

Marek: I'll send you the two endpoints after this call.

Marta: And the date?

Priya: Monday the twenty-second still works for me.

Marta: Good. So the rollout control is Priya's, for Monday the twenty-second, and Marek keeps the deprecation notice draft for the twenty-fifth. Marek, you're off the hook for the admin panel.

Marek: And for world peace?

Marta: That one's still yours.

Jonas: Can I go back to 4.2 for a second? I've been sitting on something and the longer I listen the less I like Thursday.

Marta: Go ahead.

Jonas: 4.2 includes the migration on the orders table. The one that splits the address columns out. On staging it ran in forty seconds, but staging has about two percent of production's rows. Nobody has run it against a production-sized copy. If it takes forty seconds times fifty, that's more than half an hour with the orders table locked, in the middle of a Thursday.

Marek: It's supposed to be an online migration. It shouldn't lock.

Jonas: "Supposed to" and "shouldn't" are doing a lot of work in that sentence. Last year the invoices migration was also supposed to be online, and we were down for twenty minutes.

Marek: That's fair.

Jonas: I want to rehearse it on a full copy. For that I need to refresh staging from the production snapshot, which takes most of a day, and then run the migration and time it. I can start the refresh Thursday and run the rehearsal on Friday. I can't do it earlier, the snapshot job is booked until then.

Aiko: So you're saying no Thursday release.

Jonas: I'm saying I'm not comfortable releasing a table migration on Thursday that I can only rehearse on Friday.

Aiko: That's the newsletter gone.

Marta: Is it? Can the newsletter move?

Aiko: It can say "coming next week". It's less nice. But I'd rather have that than a newsletter that says "it's live" on the day checkout was down for half an hour.

Dele: For what it's worth, an extra few days helps me too. If the regression run finds something Wednesday night, Thursday would have been a scramble anyway.

Marta: Okay. What's the new date? If the rehearsal is Friday, I don't want a Monday release with nobody having looked at the results over the weekend.

Jonas: Tuesday. I look at the numbers Friday, we have Monday to react, and we release Tuesday morning.

Marta: Tuesday the twenty-third. Aiko?

Aiko: Tuesday the twenty-third. Fine.

Marta: Then, to be clear, because we said something different half an hour ago: we are reversing the earlier decision. 4.2 does not go out this Thursday. 4.2 goes out on Tuesday the twenty-third of September. Jonas, the rehearsal is yours, by Friday the nineteenth.

Jonas: Friday the nineteenth. I'll post the timing in the release channel as soon as I have it.

Aiko: And I need to un-tell marketing. I'll confirm the new date with marketing and with support. Support had already started drafting the help article for Thursday.

Marta: By when?

Aiko: By Thursday. This Thursday, the eighteenth, before anyone asks.

Marta: Good. Does the checkout rollout move too?

Aiko: It moves with the release. Ten percent starting the week after the twenty-third.

Marta: Okay. On-call. This one is mine. We hand over on Fridays at four. I've now had three people tell me that's a terrible time, because whatever is half-broken on Friday afternoon gets explained in a hurry and then the new person has the whole weekend alone with it.

Jonas: I'm one of the three.

Dele: I'm not on the rota and even I think it's a terrible time.

Marta: So the proposal is that we hand over on Mondays at ten instead. The person who had the week also has the weekend, and the handover happens when everyone is awake and at a desk.

Marek: That makes my week on call three days longer this one time.

Marta: Not if we start it cleanly. The current rotation ends this Friday as planned. The first Monday handover would be Monday the twenty-ninth. Whoever takes over this Friday does a slightly long first shift, Friday to the Monday after next, that's Jonas, and I've already asked him.

Jonas: I said yes. I'd rather do ten days once than keep the Friday handover.

Priya: No objection from me.

Marek: Fine by me then.

Marta: Then that's decided. Handover moves from Friday to Monday at ten, first one on Monday the twenty-ninth. I'll change the schedule in PagerDuty myself. I'll have it done by Friday, the nineteenth, so that the long shift shows up correctly before it starts.

Aiko: Does that change who product calls at night?

Marta: No. Same number, it routes to whoever is on.

Marta: Dele, the end-to-end tests.

Dele: Yes. So. We have three end-to-end tests that fail roughly one run in five for no reason connected to the code. The coupon one in checkout, the avatar upload in profile, and the pagination one in search. Every time one of them fails, the pipeline goes red, someone presses retry, and twenty minutes later it's green. People have stopped reading the failures. That's the dangerous part, last week a real failure sat there for half a day because everyone assumed it was the coupon test again.

Marek: Can I make a slightly heretical suggestion? Make the end-to-end stage non-blocking. It reports, but it doesn't stop a merge. We'd still see failures.

Dele: No. With respect, no. The moment it's non-blocking, nobody looks at it at all, and in three months the suite is dead. I've watched that happen at two companies.

Priya: I'm with Dele. The suite caught the broken address form in August. Unit tests didn't.

Marek: Okay, okay. What's the alternative?

Dele: Quarantine. We move those three tests into a quarantine group. They still run, they still report, but they don't block. Everything else stays blocking. And each of the three gets a ticket with an owner, so quarantine isn't where tests go to die.

Marta: I like that better. Marek?

Marek: I can live with it. My real complaint was the retries, and that fixes the retries.

Marta: Then we quarantine the three flaky tests and the suite stays blocking. Dele, can you do the quarantine?

Dele: Yes. The config change is small. I'll quarantine the three and open a ticket for each one, by end of day tomorrow.

Marta: Wednesday the seventeenth. Thank you.

Jonas: Different topic, quickly: the outage last Tuesday. Forty minutes. We still don't have the write-up.

Marek: That's on me. I was the incident lead. I have the timeline, I haven't written the analysis.

Marta: When can we have it? I don't want it to turn into one of those post-mortems that appears two months later.

Marek: Not this week, for the reasons we just discussed. End of the month. The thirtieth.

Marta: The thirtieth of September, the post-mortem document. Okay.

Jonas: I'll review it when it's ready, just ping me.

Marta: Priya, you had something on browsers.

Priya: Yes. Safari 15. We still officially support it, and it costs me real time. The cart drawer glitch I mentioned is a Safari 15 bug. The question is whether we can drop it.

Aiko: How many users is that?

Priya: That's the thing, I don't know. The analytics dashboard groups all Safari versions together. Someone would have to pull it from the raw data.

Aiko: I'm not going to agree to dropping a browser without a number. If it's half a percent, sure. If it's five, no.

Marta: Does anyone have the number? No. Then we can't decide it today. Let's park it. It stays open until somebody has the data.

Priya: Okay. I'll keep working around it for now.

Marta: Anything else? We have four minutes.

Dele: One thing that's been bothering me. Tomas leaves at the end of October, and Tomas is the only person who really understands the billing service. Who owns billing after that?

Marek: Not me. I can read it, I can't own it.

Jonas: I can keep it running. I can't change it.

Marta: I don't have an answer. It's not something this group can settle on a Tuesday call, it depends on the hiring plan. I hear you that it's a problem. It's an open question and I'd rather say that honestly than pretend we assigned it.

Aiko: And one from me, also without an answer. The new checkout has the new consent text for saving payment details. Does legal need to sign that off before real customers see it? I assumed it was covered by the review they did in the spring, and yesterday someone told me the text changed since then.

Marta: Do we know who would decide that?

Aiko: I don't. That's sort of the problem.

Marta: Okay. I don't want to guess. Let's write it down as an open question. I'd say we need an answer before we go beyond ten percent, but nobody here can give it today.

Jonas: Agreed.

Marta: Right, that's time. Thanks, everyone. Priya, Marek, sort out the bucket API thing. Jonas, fix your microphone.

Jonas: World peace first.
