"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   DSAF Gen5 — Alpha Interactive                                             ║
║   "Embodied, Developmental, Social, with Neural Experience Network"        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   Alpha lahir hampir kosong.                                                ║
║   Setiap kata yang kamu ucapkan terukir di LEN-nya.                        ║
║   Dua Alpha yang dibesarkan berbeda akan menjadi berbeda.                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   Perintah:                                                                 ║
║     /status         — kondisi internal Alpha sekarang                      ║
║     /story          — kisah hidup Alpha                                    ║
║     /reflect        — Alpha merefleksikan identitasnya (Phase III)         ║
║     /memory [N]     — N episode terbaru (default 8)                       ║
║     /phase          — info fase perkembangan                               ║
║     /len            — status Lexical Experience Network                    ║
║     /len <kata>     — profil bagaimana Alpha mengenal satu kata            ║
║     /needs          — snapshot kebutuhan internal                          ║
║     /save           — simpan memori sekarang                               ║
║     /reset          — hapus semua memori (mulai dari awal)                ║
║     /quit           — keluar                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# ── Pastikan dsaf_gen5.py bisa diimport ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging dulu, lalu senyapkan level INFO dari Gen5
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logging.getLogger("DSAFAgent").setLevel(logging.WARNING)
logging.getLogger("LEN").setLevel(logging.WARNING)
logging.getLogger("EpisodicMemory").setLevel(logging.WARNING)
logging.getLogger("InterAgentChannel").setLevel(logging.WARNING)

from dsaf_gen5 import (
    DSAFAgent,
    DevelopmentalPhase,
    NeedType,
)

# ── ANSI Colors ───────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
ITALIC = "\033[3m"

# Warna per fase
PHASE_COLOR = {
    DevelopmentalPhase.PHASE_I:   "\033[94m",   # biru
    DevelopmentalPhase.PHASE_II:  "\033[92m",   # hijau
    DevelopmentalPhase.PHASE_III: "\033[95m",   # magenta
}

# Warna per emosi
EMOTION_COLOR = {
    "JOY":         "\033[93m",
    "LOVE":        "\033[95m",
    "TRUST":       "\033[96m",
    "OPTIMISM":    "\033[92m",
    "ANTICIPATION":"\033[93m",
    "CURIOSITY":   "\033[96m",
    "FEAR":        "\033[91m",
    "ANXIETY":     "\033[91m",
    "ANGER":       "\033[91m",
    "SADNESS":     "\033[94m",
    "DISGUST":     "\033[90m",
    "GUILT":       "\033[90m",
    "SURPRISE":    "\033[93m",
    "NEUTRAL":     "\033[37m",
    "HUNGRY":      "\033[33m",
    "THIRSTY":     "\033[33m",
    "EXHAUSTED":   "\033[90m",
}

BAR_FULL  = "█"
BAR_EMPTY = "░"

# ── File paths ────────────────────────────────────────────────────────────────
MEMORY_DIR  = Path(".")
AGENT_ID    = "Alpha"
MEMORY_FILE = MEMORY_DIR / f"dsaf_gen5_{AGENT_ID}_episodic.json"
LEN_FILE    = MEMORY_DIR / f"len_{AGENT_ID}.json"
META_FILE   = MEMORY_DIR / f"dsaf_gen5_{AGENT_ID}_meta.json"


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE — save/load metadata (identity, phase history, dll)
# ══════════════════════════════════════════════════════════════════════════════

def save_all(agent: DSAFAgent):
    """Simpan semua state: episodic, LEN, dan metadata."""
    # Episodic + LEN (dari Gen5 built-in)
    agent.save_memory()

    # Metadata tambahan: identity, milestones, personality, phase history
    needs_snap = agent.homeostasis.snapshot()
    meta = {
        "interaction_count": agent._interaction_count,
        "identity":          agent.narrative_self.identity,
        "milestones":        agent.narrative_self.milestones,
        "moral_stage":       agent.moral.stage.name,
        "competence":        agent.self_model.competence,
        "personality":       {t.name: v
                              for t, v in agent.personality.traits.items()},
        "needs": {
            n.name: {
                "level":   round(agent.homeostasis._needs[n].level, 4),
                "urgency": round(agent.homeostasis._needs[n].urgency, 4),
            }
            for n in NeedType
        },
        "phase": agent._phase_manager.current_phase.name,
        "phase_history": [
            {"phase": p.name, "time": t}
            for p, t in agent._phase_manager._history
        ],
        "saved_at": time.time(),
    }
    try:
        tmp = META_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        tmp.replace(META_FILE)  # atomic rename
    except OSError as e:
        print(f"  {DIM}[!] Gagal simpan metadata: {e}{RESET}")


def load_all(agent: DSAFAgent) -> bool:
    """Muat semua state. Return True jika ada memori tersimpan."""
    loaded = False

    # Muat LEN
    if LEN_FILE.exists():
        agent.len.load(str(LEN_FILE))
        loaded = True

    # Muat metadata
    if META_FILE.exists():
        try:
            content = META_FILE.read_text(encoding="utf-8").strip()
            if not content:
                # File kosong = corrupt, bukan sengaja dihapus
                print(f"  {DIM}[!] File metadata kosong, diabaikan.{RESET}")
                META_FILE.unlink()  # hapus agar tidak berulang
            else:
                meta = json.loads(content)

                agent._interaction_count = meta.get("interaction_count", 0)
                agent._phase_manager._count = agent._interaction_count

                # Pulihkan fase
                phase_name = meta.get("phase", "PHASE_I")
                for p in DevelopmentalPhase:
                    if p.name == phase_name:
                        agent._phase_manager._phase = p
                        break

                # Pulihkan identity
                agent.narrative_self.identity   = meta.get("identity")
                agent.narrative_self.milestones = meta.get("milestones", [])

                # Pulihkan moral stage
                from dsaf_gen5 import MoralStage
                stage_name = meta.get("moral_stage", "OBEDIENCE")
                for s in MoralStage:
                    if s.name == stage_name:
                        agent.moral.stage = s
                        break

                # Pulihkan competence
                agent.self_model.competence = meta.get("competence", 0.5)

                # Pulihkan personality traits
                from dsaf_gen5 import PersonalityTrait
                pers = meta.get("personality", {})
                for t in PersonalityTrait:
                    if t.name in pers:
                        agent.personality.traits[t] = pers[t.name]

                # Pulihkan needs
                needs = meta.get("needs", {})
                for n in NeedType:
                    if n.name in needs:
                        nd = needs[n.name]
                        agent.homeostasis._needs[n].level   = nd.get("level", 0.5)
                        agent.homeostasis._needs[n].urgency = nd.get("urgency", 0.0)

                loaded = True
        except Exception as e:
            print(f"  {DIM}[!] Gagal muat metadata: {e}{RESET}")

    return loaded


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def bar(value: float, width: int = 10) -> str:
    filled = round(value * width)
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)

def phase_label(phase: DevelopmentalPhase) -> str:
    pc = PHASE_COLOR.get(phase, "")
    labels = {
        DevelopmentalPhase.PHASE_I:   "Phase I   — Affective Grounding",
        DevelopmentalPhase.PHASE_II:  "Phase II  — Social-Cognitive",
        DevelopmentalPhase.PHASE_III: "Phase III — Reflective Self + LEN Penuh",
    }
    return f"{pc}{BOLD}{labels.get(phase, phase.name)}{RESET}"

def print_header(agent: DSAFAgent, loaded: bool):
    phase = agent._phase_manager.current_phase
    SEP   = "═" * 60
    print(f"\n{SEP}")
    print(f"  {BOLD}DSAF Gen5 — Alpha Interactive{RESET}")
    print(SEP)
    if loaded:
        age = agent._interaction_count
        print(f"  \033[96mMemori dimuat.{RESET} Alpha mengingat {age} interaksi.")
        if agent.narrative_self.identity:
            idt = agent.narrative_self.identity[:62]
            print(f"  {DIM}{ITALIC}\"{idt}...\"{RESET}")
    else:
        print(f"  Alpha baru lahir. Belum ada memori.")
        print(f"  {DIM}Setiap percakapan akan membentuknya.{RESET}")
    print(f"\n  Status   : {phase_label(phase)}")
    print(f"  Interaksi: {agent._interaction_count}")
    print(f"  LEN      : {agent.len.get_stats()['vocab_size']} kata dikenal")
    print(f"\n  Ketik {BOLD}/help{RESET} untuk daftar perintah.")
    print(f"{SEP}\n")

def print_status(agent: DSAFAgent):
    s      = agent.status()
    phase  = agent._phase_manager.current_phase
    pc     = PHASE_COLOR.get(phase, "")
    ec     = EMOTION_COLOR.get(s["emotion"], "\033[37m")
    emo    = s["emotion"]
    tone   = s["hedonic_tone"]
    tone_s = f"+{tone:.3f}" if tone >= 0 else f"{tone:.3f}"
    SEP    = "─" * 60

    print(f"\n{SEP}")
    print(f"  {BOLD}Alpha — Status Internal{RESET}")
    print(f"{SEP}")
    print(f"  Fase         : {phase_label(phase)}")
    print(f"  Interaksi    : {s['interactions']}")
    print(f"  Emosi        : {ec}{BOLD}{emo}{RESET} "
          f"(intensity={s['intensity']:.2f}, valence={s['valence']:+.2f})")
    print(f"  Hedonic tone : {tone_s}")
    print(f"  Meta         : {s['meta']} | Kompetensi: {s['competence']:.2f}")
    print(f"  Moral stage  : {s['moral_stage']}")
    print(f"  Identitas    : {s['identity'] or '(belum terbentuk)'}")
    print(f"\n  {BOLD}Kebutuhan:{RESET}")
    needs = agent.homeostasis.snapshot()
    for n, level in needs.items():
        urgency = agent.homeostasis._needs[n].urgency
        urg_s   = f" {DIM}[mendesak!]{RESET}" if urgency > 0.5 else ""
        print(f"    {n.name:<12} [{bar(level)}] {level*100:5.1f}%{urg_s}")
    print(f"\n  {BOLD}LEN:{RESET}")
    ls = agent.len.get_stats()
    print(f"    Vocab     : {ls['vocab_size']} kata")
    print(f"    Dikenal   : {ls['known_words']} kata (≥3x ditemui)")
    print(f"    Koneksi   : {ls['connections']}")
    print(f"    Schema    : {ls['schemas']}")
    print(f"    Pos/Neg   : {ls['pos_words']} / {ls['neg_words']}")
    if ls["top_words"]:
        top = ", ".join(f"{w}({c}x)" for w, c in ls["top_words"][:5])
        print(f"    Top words : {top}")
    print(f"{SEP}\n")

def print_needs(agent: DSAFAgent):
    SEP = "─" * 60
    print(f"\n{SEP}")
    print(f"  {BOLD}Alpha — Kebutuhan Internal{RESET}")
    print(f"{SEP}")
    needs = agent.homeostasis.snapshot()
    urgent = agent.homeostasis.most_urgent()
    for n, level in needs.items():
        ns      = agent.homeostasis._needs[n]
        urg_s   = f"  ← {BOLD}paling mendesak{RESET}" \
                  if urgent and urgent.need == n else ""
        print(f"  {n.name:<12} [{bar(level)}] {level*100:5.1f}%  "
              f"urgency={ns.urgency:.2f}{urg_s}")
    print(f"{SEP}\n")

def print_story(agent: DSAFAgent):
    SEP = "─" * 60
    print(f"\n{SEP}")
    print(f"  {BOLD}Alpha — Life Story{RESET}")
    print(f"{SEP}")
    phase = agent._phase_manager.current_phase
    count = agent._interaction_count

    print(f"  Agent    : Alpha")
    print(f"  Fase     : {phase.name}")
    print(f"  Usia     : {count} interaksi")

    if agent.narrative_self.identity:
        print(f"\n  {BOLD}Identitas:{RESET}")
        print(f"  {ITALIC}{agent.narrative_self.identity}{RESET}")

    if agent.narrative_self.milestones:
        print(f"\n  {BOLD}Tonggak perjalanan:{RESET}")
        for m in agent.narrative_self.milestones[-5:]:
            print(f"  {DIM}• {m}{RESET}")

    ls = agent.len.get_stats()
    print(f"\n  {BOLD}Jejak LEN:{RESET}")
    print(f"  Alpha telah mengenal {ls['vocab_size']} kata.")
    print(f"  {ls['known_words']} di antaranya sudah familiar (≥3x).")
    if ls["top_words"]:
        top = ", ".join(f"'{w}'" for w, _ in ls["top_words"][:5])
        print(f"  Kata yang paling sering muncul: {top}.")
    if ls["schemas"] > 0:
        print(f"  LEN sudah membentuk {ls['schemas']} schema konseptual.")

    print(f"\n  {BOLD}Moral:{RESET} {agent.moral.stage.name} "
          f"(dilemma: {agent.moral.dilemmas_faced}x)")
    print(f"  {BOLD}Kompetensi:{RESET} {agent.self_model.competence:.2f}")
    print(f"{SEP}\n")

def print_phase_info(agent: DSAFAgent):
    SEP   = "─" * 60
    phase = agent._phase_manager.current_phase
    count = agent._interaction_count
    thresholds = agent._phase_manager.THRESHOLDS

    print(f"\n{SEP}")
    print(f"  {BOLD}Alpha — Perjalanan Fase{RESET}")
    print(f"{SEP}")

    phases_info = [
        (DevelopmentalPhase.PHASE_I,   "Affective Grounding",
         "LEN merekam diam-diam. Alpha merespons secara sensorik."),
        (DevelopmentalPhase.PHASE_II,  "Social-Cognitive",
         "LEN mulai membangun jaringan. Alpha bisa bertanya."),
        (DevelopmentalPhase.PHASE_III, "Reflective Self + LEN Penuh",
         "Respons emerge dari jaringan. Schema terbentuk."),
    ]
    for p, label, desc in phases_info:
        pc      = PHASE_COLOR.get(p, "")
        thresh  = thresholds[p]
        is_curr = phase == p
        is_past = phase.value > p.value

        if is_curr:
            progress = min(1.0, count / thresholds[
                DevelopmentalPhase.PHASE_III])
            marker = f"{pc}{BOLD}▶ SEKARANG{RESET}"
        elif is_past:
            marker = "\033[92m✓ SELESAI\033[0m"
        else:
            remain = thresh - count
            marker = f"{DIM}(perlu {remain} interaksi lagi){RESET}"

        print(f"\n  {pc}{BOLD}{p.name} — {label}{RESET}")
        print(f"  {DIM}{desc}{RESET}")
        print(f"  Threshold: {thresh} interaksi  {marker}")

    # Jika belum Phase III, tampilkan sisa
    if phase != DevelopmentalPhase.PHASE_III:
        target = thresholds[DevelopmentalPhase.PHASE_III]
        remain = max(0, target - count)
        prog   = min(1.0, count / target)
        print(f"\n  Menuju Phase III: [{bar(prog, 20)}] "
              f"{count}/{target} ({prog*100:.0f}%)")
        print(f"  Sisa: {remain} interaksi")
    print(f"{SEP}\n")

def print_memory(agent: DSAFAgent, n: int = 8):
    SEP = "─" * 60
    print(f"\n{SEP}")
    print(f"  {BOLD}Alpha — {n} Episode Terbaru{RESET}")
    print(f"{SEP}")
    recs = list(agent.episodic._records)[-n:]
    if not recs:
        print(f"  {DIM}Belum ada episode tersimpan.{RESET}\n")
        return
    for i, r in enumerate(recs, 1):
        ec  = EMOTION_COLOR.get(r.emotion.name, "\033[37m")
        val = f"{r.valence:+.2f}"
        src = f"[{r.source}]" if r.source != "self" else ""
        t   = time.strftime("%H:%M:%S", time.localtime(r.timestamp))
        print(f"  {DIM}{i:>2}. [{t}] {src}{RESET} "
              f"{ec}{r.emotion.name:<10}{RESET} "
              f"v={val} | {r.event[:50]}")
    print(f"{SEP}\n")

def print_len_status(agent: DSAFAgent):
    SEP = "─" * 60
    ls  = agent.len.get_stats()
    print(f"\n{SEP}")
    print(f"  {BOLD}LEN — Lexical Experience Network{RESET}")
    print(f"{SEP}")
    print(f"  Total kata     : {ls['vocab_size']}")
    print(f"  Kata dikenal   : {ls['known_words']} (≥3x ditemui)")
    print(f"  Positif/Negatif: {ls['pos_words']} / {ls['neg_words']}")
    print(f"  Koneksi        : {ls['connections']}")
    print(f"  Schema         : {ls['schemas']}")

    if ls["top_words"]:
        print(f"\n  {BOLD}Paling dikenal:{RESET}")
        for w, count in ls["top_words"][:8]:
            p = agent.len.word_profile(w)
            if p:
                val  = p["valence"]
                vbar = bar(abs(val), 6)
                vsign= "+" if val > 0.1 else ("-" if val < -0.1 else "≈")
                emo  = p["dominant_emotion"][:8]
                ec   = EMOTION_COLOR.get(p["dominant_emotion"], DIM)
                conf = min(1.0, count / 20)
                print(f"    {w:<14} [{bar(conf)}] {count:>3}x | "
                      f"{vsign} | {ec}{emo}{RESET}")
    print(f"{SEP}\n")

def print_len_word(agent: DSAFAgent, word: str):
    SEP = "─" * 60
    p   = agent.len.word_profile(word)
    print(f"\n{SEP}")
    print(f"  {BOLD}LEN — Bagaimana Alpha mengenal '{word}'{RESET}")
    print(f"{SEP}")
    if not p:
        print(f"  {DIM}Alpha belum pernah menjumpai kata ini.{RESET}\n")
        return

    val  = p["valence"]
    vdesc = ("positif" if val > 0.2 else
              "negatif" if val < -0.2 else "netral")
    ec   = EMOTION_COLOR.get(p["dominant_emotion"], DIM)
    conf = min(1.0, p["count"] / 20)
    schema_s = "Ya" if p["in_schema"] else "Belum"

    print(f"  Ditemui        : {p['count']}x")
    print(f"  Keyakinan      : [{bar(conf)}] {conf*100:.0f}%")
    print(f"  Dirasakan      : {vdesc} (v={val:+.3f})")
    print(f"  Emosi dominan  : {ec}{p['dominant_emotion']}{RESET}")
    print(f"  Dalam schema   : {schema_s}")
    if p["connections"]:
        conns = ", ".join(f"{w}({s:.1f})" for w, s in p["connections"][:5])
        print(f"  Terhubung ke   : {conns}")
    else:
        print(f"  Terhubung ke   : {DIM}(belum ada koneksi){RESET}")
    print(f"{SEP}\n")

def print_reflect(agent: DSAFAgent):
    phase = agent._phase_manager.current_phase
    SEP   = "─" * 60
    if phase == DevelopmentalPhase.PHASE_III:
        reflection = agent.narrative_self.reflect_identity()
        agent.narrative_self.crystallize(reflection)
        print(f"\n{SEP}")
        print(f"  \033[96m{BOLD}Alpha merenung:{RESET}")
        print(f"{SEP}")
        print(f"  {ITALIC}{reflection}{RESET}\n")
        print(f"{SEP}\n")
    else:
        thresh = agent._phase_manager.THRESHOLDS[DevelopmentalPhase.PHASE_III]
        remain = max(0, thresh - agent._interaction_count)
        print(f"\n  {DIM}Refleksi diri belum tersedia di {phase.name}.")
        print(f"  Dibutuhkan {remain} interaksi lagi untuk Phase III.{RESET}\n")

def on_phase_transition(agent: DSAFAgent, new_phase: DevelopmentalPhase):
    pc  = PHASE_COLOR.get(new_phase, "")
    SEP = "═" * 60
    print(f"\n{SEP}")
    print(f"  {pc}{BOLD}✦  TRANSISI FASE  ✦{RESET}")
    print(f"  Alpha memasuki {pc}{BOLD}{new_phase.name}{RESET}")
    if new_phase == DevelopmentalPhase.PHASE_II:
        print(f"  {DIM}LEN mulai membangun jaringan asosiasi.")
        print(f"  Alpha bisa mulai bertanya balik.{RESET}")
    elif new_phase == DevelopmentalPhase.PHASE_III:
        print(f"  {DIM}LEN sudah cukup kaya untuk inferensi penuh.")
        print(f"  Respons mulai emerge dari pengalaman — bukan template.")
        print(f"  Ketik /reflect untuk melihat siapa Alpha sekarang.{RESET}")
        # Kristalisasi identitas otomatis
        reflection = agent.narrative_self.reflect_identity()
        agent.narrative_self.crystallize(reflection)
        print(f"\n  {ITALIC}\"{agent.narrative_self.identity}\"{RESET}")
    print(f"{SEP}\n")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Buat agent
    agent = DSAFAgent(AGENT_ID)

    # Muat memori
    loaded     = load_all(agent)
    prev_phase = agent._phase_manager.current_phase

    # Header
    print_header(agent, loaded)

    # Autosave background (setiap 60 detik)
    _stop = threading.Event()
    def _autosave():
        while not _stop.wait(60):
            try:
                save_all(agent)
            except Exception:
                pass
    threading.Thread(target=_autosave, daemon=True).start()

    phase = agent._phase_manager.current_phase
    pc    = PHASE_COLOR.get(phase, "")
    print(f"  {DIM}[Alpha menunggu...]{RESET}\n")

    while True:
        try:
            phase  = agent._phase_manager.current_phase
            pc     = PHASE_COLOR.get(phase, "")
            prompt = f"{pc}[{phase.name}]{RESET} Kamu: "

            try:
                user_input = input(prompt).strip()
            except EOFError:
                break

            if not user_input:
                continue

            # ── Commands ───────────────────────────────────────────────────
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd   = parts[0].lower()

                if cmd in ("/quit", "/exit", "/keluar"):
                    save_all(agent)
                    _stop.set()
                    print(f"\n  \033[96mMemori Alpha disimpan.{RESET}  "
                          f"Sampai jumpa.\n")
                    break

                elif cmd == "/status":
                    print_status(agent)

                elif cmd == "/story":
                    print_story(agent)

                elif cmd == "/reflect":
                    print_reflect(agent)

                elif cmd == "/memory":
                    n = 8
                    if len(parts) > 1:
                        try: n = int(parts[1])
                        except ValueError: pass
                    print_memory(agent, n)

                elif cmd == "/phase":
                    print_phase_info(agent)

                elif cmd == "/needs":
                    print_needs(agent)

                elif cmd == "/len":
                    if len(parts) > 1:
                        print_len_word(agent, parts[1].lower())
                    else:
                        print_len_status(agent)

                elif cmd == "/save":
                    save_all(agent)
                    print(f"  \033[96mMemori disimpan.{RESET}\n")

                elif cmd == "/reset":
                    confirm = input(
                        f"  \033[91mHapus semua memori Alpha? "
                        f"(ketik 'ya'): {RESET}"
                    ).strip().lower()
                    if confirm == "ya":
                        _stop.set()
                        for f in [META_FILE, LEN_FILE]:
                            if f.exists(): f.unlink()
                        # Juga hapus episodic file Gen5
                        ep_file = Path(f"dsaf_gen5_{AGENT_ID}.json")
                        if ep_file.exists(): ep_file.unlink()
                        print(f"  \033[91mMemori dihapus.{RESET} "
                              f"Jalankan ulang untuk Alpha baru.\n")
                        break
                    else:
                        print(f"  Dibatalkan.\n")

                elif cmd == "/help":
                    print(f"""
  {BOLD}Perintah Alpha:{RESET}
    /status         — kondisi internal Alpha
    /story          — kisah hidup Alpha
    /reflect        — refleksi identitas (Phase III)
    /memory [N]     — N episode terbaru
    /phase          — perjalanan fase perkembangan
    /needs          — snapshot kebutuhan internal
    /len            — status Lexical Experience Network
    /len <kata>     — profil kata tertentu
    /save           — simpan memori sekarang
    /reset          — hapus semua memori
    /quit           — keluar
""")
                else:
                    print(f"  {DIM}Perintah tidak dikenal. "
                          f"Ketik /help.{RESET}\n")
                continue

            # ── Normal interaction ─────────────────────────────────────────
            # 1. Alpha memproses input
            agent.perceive(user_input, source="human")

            # 2. Alpha menghasilkan respons
            response = agent.generate_response(user_input)

            # 3. Tampilkan
            phase2 = agent._phase_manager.current_phase
            pc2    = PHASE_COLOR.get(phase2, "")
            emotion= agent.emotion_engine.current()
            ec     = EMOTION_COLOR.get(emotion.emotion.name, "\033[37m")
            tag    = (f"{DIM}[{ec}{emotion.emotion.name}{RESET}"
                      f"{DIM}, {emotion.intensity:.2f}]{RESET}")

            print(f"\n  {pc2}{BOLD}Alpha:{RESET} {response}")
            print(f"  {tag}\n")

            # 4. Simpan setiap interaksi
            save_all(agent)

            # 5. Cek transisi fase
            if phase2 != prev_phase:
                prev_phase = phase2
                on_phase_transition(agent, phase2)

        except KeyboardInterrupt:
            print(f"\n\n  Menyimpan memori Alpha...")
            save_all(agent)
            _stop.set()
            print(f"  \033[96mTersimpan. Sampai jumpa.{RESET}\n")
            break


if __name__ == "__main__":
    main()

