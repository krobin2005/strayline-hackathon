# Strayline Desk, explained simply

## The one-sentence version

It's a ChatGPT-style helper that runs **entirely on one laptop with no internet**. A college's IT security team can drop in screenshots, voicemails, documents, videos, code requests or network logs and get useful answers, without sending private data to any company.

---

## Why does this need to exist?

Picture the two or three people who keep a whole college safe from hackers. Every day they get:

- a screenshot of a weird email: "is this a scam?"
- a voicemail: "someone called pretending to be IT and asked for my password"
- a screen recording from a student: "this pop-up took over my laptop"
- the college's rulebook: "who do I call when an account gets hacked?"
- a giant list of every network connection that happened today

All of that contains **private information about real students and staff**. They can't paste it into ChatGPT, because that sends it to an outside company. So today they do it all by hand.

**Strayline Desk is an AI helper that never leaves the laptop.** Same kind of help, but the data stays in the building.

---

## What the hackathon asked for (and how we match it)

The challenge: *build a multimodal AI that runs on your own machine, using free open models, for a real user.* "Multimodal" just means it handles different kinds of input. Judges want to see five:

| Input | What judges want | What ours does |
|---|---|---|
| 🖼 **Image** | Describe a photo, answer questions | "Is this email screenshot a scam? Why?" |
| 🎧 **Audio** | Write down what's said, answer questions, name sounds | Writes out a voicemail, says what the caller wanted, names sounds like "dog barking" |
| 📄 **Text** | Answer questions about a document, and admit when the answer isn't in it | Answers from the rulebook with the page number, or says "This isn't in the document." |
| 💻 **Code** | Write working code | Writes Python code, **runs it to prove it works**, and shows the result |
| 🎬 **Video** | Describe a clip, answer questions | "What happened in this screen recording?" |
| 📈 **Logs** *(our bonus)* | | Our Strayline detector reads a whole day of network traffic and finds the attacks |

---

## How it works

### The "brains" (the AI models)
We use two free AI models that we downloaded onto the laptop. Think of them as two employees:

- **Qwen3-VL ("the eyes")** looks at pictures and video frames.
- **Gemma 4 ("the ears and the writer")** listens to speech, reads documents, writes code and writes the answers.

Plus a small specialist:
- **The sound classifier ("the sound expert")** is trained only to recognize everyday sounds (chainsaw, baby crying, rain, rooster…). Gemma was bad at naming sounds by itself (about 1 in 10 right), so we added this specialist (now most are right).

A program called **Ollama** runs the models on the laptop, the way Spotify plays music files.

### The traffic cop
When you upload something, plain code (not AI) looks at the file type and sends it to the right worker:
- image → the eyes
- audio → the sound expert, then the ears
- video → we grab about 10 still frames and send them to the eyes
- document → we find the most relevant paragraphs, then the writer answers only from those
- code request → the writer writes code, and we run it in a locked box
- logs → our detector

### Tricks that make it trustworthy
- **"This isn't in the document."** The writer is told to answer *only* from the document. If the answer isn't there, it has to say so instead of making something up.
- **The code sandbox.** Generated code runs in a locked box: no internet, a 10-second time limit, a throwaway folder. If it breaks, the error goes back to the AI once to fix it.
- **Show your work.** Every answer shows what it was based on (the transcript, the page, the code's output) and how long it took.

### The Strayline detector (the logs part)
This is the part from Kyle's earlier research, rebuilt from scratch this week. A network keeps a record of every connection (who talked to whom, how much, how fast). A normal day has about **half a million** of them. Nobody can read that.

The detector works like two security guards:
1. **Guard 1 ("seen it before")** learned what known attacks look like from example data.
2. **Guard 2 ("that's weird")** learned what *normal* traffic looks like and flags anything far from normal. This catches attacks nobody has seen before.

If either guard raises a hand, the connection is flagged. The guards are tuned so they only bother you about **2% of normal traffic**. The flags are then grouped by which computer did them, so 170,000 flags become **33 incidents**, sorted biggest first. The AI then writes a short briefing: "look at #1 first, here's why."

**Test:** on a day of traffic the detector had never seen, which included a kind of attack it was never trained on, the attack came out as **incident #1**.

---

## How well does it work? (our test results)

The organizers gave us 100 practice questions in the same format the judges will use on Friday. Our test program runs all 100 through the app and checks the answers automatically.

| Input | Score | How fast |
|---|---|---|
| Image | 23 / 25 | ~8 s |
| Audio | 18 / 20 | ~7 s |
| Text | **20 / 20** | ~5 s |
| Video | 13 / 15 | ~60 s (the slow one) |
| Code | 19 / 20 | ~19 s |
| **Total** | **93 / 100** (71 proven by the strict auto-checker; the rest checked by our AI assistant, to be confirmed by us) | |

**What it's bad at (we say this out loud, and judges like honesty):**
- **Video is slow,** about a minute per clip, and it struggles to count things that appear one at a time.
- **Some sounds get a vague label,** like "vehicle" instead of "helicopter".
- **It miscounted people in one crowded photo** (7 instead of 6).

---

## How judges score us (and where we're strong)

| What they score | Weight | Us |
|---|---|---|
| All five inputs working + our own test results | 30% | ✅ all five work, and we have a 100-item test |
| A real app that works live and is easy to use | 25% | ✅ one simple chat page, works on a phone too |
| Explaining our models and their limits | 20% | ✅ we tested several models and can say why we picked these |
| A specific user with a real problem | 15% | ✅ college IT security; team rehearsal planned; external validation remains open |
| Answering judges' questions | 10% | practice! |

---

## How to run it (on Kyle's laptop)

1. Open the **Ollama** app (llama icon in the menu bar).
2. In Terminal, inside the project folder:
   ```bash
   .venv/bin/python -m desk
   ```
3. Open **http://localhost:8000** in a browser. For a phone, use the second address it prints (same Wi-Fi).
4. Wait about a minute for the models to load the first time. Then type a question or press **＋** to attach a file.

New laptop? Run `sh setup.sh` once first (it downloads about 14 GB of models).

---

## Words you might hear

- **Model:** the AI "brain" file. Ours are free to download ("open-weight").
- **Local / offline:** runs on the laptop itself; no internet needed.
- **Multimodal:** handles more than just text (pictures, sound, video…).
- **Prompt:** the instructions we give the AI.
- **Token:** a chunk of text or image the AI processes. More tokens means slower.
- **Sandbox:** a locked box where untrusted code can run safely.
- **False alarm rate:** how often the detector flags normal, harmless traffic (ours: 0.44%).
- **Incident:** a group of alerts from one computer around the same time.
- **Harness:** our test program that runs all the practice questions and scores them.
