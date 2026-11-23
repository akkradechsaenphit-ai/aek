"""Game catalog: three movement games, each a list of spoken steps that the
elder screen plays one by one.

Step fields:
  say      what the screen shows and speaks
  emoji    big picture for the step
  seconds  how long the step lasts
  reps     count aloud this many times, one every `beat` seconds
  detect   with the camera on, count a rep only when the camera sees this move
           (arms_up | clap); without the camera the screen counts on the beat
  motion   only fill the progress bar while the radar or camera sees movement
  confirm  wait until the elder taps this button
"""

GAMES = [
    {
        "id": "arm_sky",
        "title": "ยกแขนแตะฟ้า",
        "emoji": "🙌",
        "kind": "move",
        "minutes": 2,
        "seated_ok": True,
        "knee_safe": True,
        "desc": "ยกแขนสองข้างขึ้นสูงแล้ววางลง ทำได้ทั้งนั่งและยืน",
        "steps": [
            {"emoji": "🪑", "say": "นั่งหลังตรง หรือยืนจับพนักเก้าอี้ไว้นะคะ", "seconds": 5},
            {"emoji": "🙌", "say": "ยกแขนสองข้างขึ้นแตะฟ้า แล้ววางลง นับไปพร้อมกันนะคะ", "reps": 10, "beat": 3, "detect": "arms_up"},
            {"emoji": "🌬️", "say": "หายใจเข้าลึกๆ แล้วผ่อนออกช้าๆ", "seconds": 6},
        ],
    },
    {
        "id": "march",
        "title": "ย่ำเท้าตามจังหวะ",
        "emoji": "🥁",
        "kind": "move",
        "minutes": 2,
        "seated_ok": True,
        "knee_safe": True,
        "desc": "ย่ำเท้าอยู่กับที่ หลอดพลังจะเต็มเมื่อกล้องหรือเรดาร์เห็นว่ากำลังขยับ",
        "steps": [
            {"emoji": "🧍", "say": "ลุกขึ้นยืนจับพนักเก้าอี้ไว้ หรือนั่งย่ำก็ได้ค่ะ", "seconds": 6},
            {"emoji": "🥁", "say": "ย่ำเท้าอยู่กับที่ ยกเข่าขึ้นสูงๆ เลยค่ะ", "seconds": 45, "motion": True},
            {"emoji": "🌬️", "say": "พักหายใจสักครู่นะคะ", "seconds": 6},
        ],
    },
    {
        "id": "clap",
        "title": "ปรบมือตามจังหวะ",
        "emoji": "👏",
        "kind": "move",
        "minutes": 1,
        "seated_ok": True,
        "knee_safe": True,
        "desc": "ปรบมือตามเสียงนับ เร็วขึ้นทีละนิด ฝึกสมาธิและข้อมือ",
        "steps": [
            {"emoji": "👐", "say": "เตรียมมือให้พร้อม ปรบมือตามเสียงนับนะคะ", "seconds": 4},
            {"emoji": "👏", "say": "ปรบช้าๆ ก่อนค่ะ", "reps": 8, "beat": 2, "detect": "clap"},
            {"emoji": "👏", "say": "เร็วขึ้นอีกนิดนะคะ", "reps": 10, "beat": 1.2, "detect": "clap"},
            {"emoji": "🎉", "say": "ปรบมือให้ตัวเองดังๆ เลยค่ะ", "seconds": 4},
        ],
    },
]

BY_ID = {g["id"]: g for g in GAMES}


def summary() -> list[dict]:
    """Catalog without the step details (for menus and the AI prompt)."""
    keys = ("id", "title", "emoji", "kind", "minutes", "seated_ok", "knee_safe", "desc")
    return [{k: g[k] for k in keys} for g in GAMES]
