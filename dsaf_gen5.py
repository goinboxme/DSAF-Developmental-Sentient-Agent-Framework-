"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   DEVELOPMENTAL SENTIENT AGENT FRAMEWORK  —  Gen 5                         ║
║   "Embodied, Developmental, Social, with Neural Experience Network"        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NEW IN GEN5:                                                               ║
║    • Lexical Experience Network (LEN) — jaringan saraf yang tumbuh dari    ║
║      nol, terukir oleh pengalaman unik setiap agent.                        ║
║    • Setiap agent punya "otak" yang benar-benar unik — seperti kembar      ║
║      identik yang berbeda karena pengalaman.                                ║
║    • Tidak ada pre-training. Semua bobot tumbuh dari interaksi nyata.      ║
║    • Phase I: LEN belajar valensi emosional                                 ║
║    • Phase II: LEN mulai membangun asosiasi antar konsep                   ║
║    • Phase III: LEN mampu inferensi kontekstual penuh                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import heapq

# [IMPORT] Semua komponen dari Gen4 akan diimpor
# Untuk kejelahan, kita tulis ulang dengan LEN sebagai tambahan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

MEMORY_FILE_TEMPLATE = "dsaf_gen5_{agent_id}.json"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 0 — ENUMS & PRIMITIVES (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class NeedType(Enum):
    ENERGY      = auto()
    HYDRATION   = auto()
    SAFETY      = auto()
    CURIOSITY   = auto()
    CONNECTION  = auto()
    COMPETENCE  = auto()
    MEANING     = auto()


class EmotionType(Enum):
    JOY          = auto()
    SADNESS      = auto()
    ANGER        = auto()
    FEAR         = auto()
    TRUST        = auto()
    DISGUST      = auto()
    SURPRISE     = auto()
    ANTICIPATION = auto()
    LOVE         = auto()
    ANXIETY      = auto()
    OPTIMISM     = auto()
    GUILT        = auto()
    CURIOSITY    = auto()
    HUNGRY       = auto()
    THIRSTY      = auto()
    EXHAUSTED    = auto()
    NEUTRAL      = auto()


class PersonalityTrait(Enum):
    OPENNESS          = auto()
    CONSCIENTIOUSNESS = auto()
    EXTRAVERSION      = auto()
    AGREEABLENESS     = auto()
    NEUROTICISM       = auto()


class MoralStage(Enum):
    OBEDIENCE        = 1
    SELF_INTEREST    = 2
    SOCIAL_APPROVAL  = 3
    LAW_AND_ORDER    = 4
    SOCIAL_CONTRACT  = 5
    UNIVERSAL_ETHICS = 6


class DevelopmentalPhase(Enum):
    PHASE_I   = 1   # Affective Grounding (0-20)
    PHASE_II  = 2   # Social-Cognitive (20-100)
    PHASE_III = 3   # Reflective Self (100+)


class ActionType(Enum):
    MOVE  = "move"
    REST  = "rest"
    EAT   = "eat"
    DRINK = "drink"
    WAIT  = "wait"
    COMMUNICATE = "communicate"


class GoalType(Enum):
    EXPLORE    = "explore"
    FIND_FOOD  = "find_food"
    FIND_WATER = "find_water"
    STAY_SAFE  = "stay_safe"
    SOCIALIZE  = "socialize"
    UNDERSTAND = "understand"


class AgentIntent(Enum):
    EXPLORING       = "exploring"
    SEARCHING_FOOD  = "searching_food"
    SEARCHING_WATER = "searching_water"
    IDLE            = "idle"
    FLEEING         = "fleeing"
    SOCIALIZING     = "socializing"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — PHYSICAL BODY & ENVIRONMENT (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BodyState:
    energy:     float = 100.0
    hydration:  float = 100.0
    position:   int   = 0
    alive:      bool  = True
    WORLD_SIZE: int   = field(default=16, init=False, repr=False)

    def apply_action(self, action: ActionType):
        if action == ActionType.MOVE:
            self.position  = (self.position + 1) % self.WORLD_SIZE
            self.energy    -= 5.0
            self.hydration -= 2.0
        elif action == ActionType.REST:
            self.energy    += 3.0
        elif action == ActionType.EAT:
            self.energy    += 25.0
        elif action == ActionType.DRINK:
            self.hydration += 25.0
        elif action == ActionType.WAIT:
            self.energy    -= 0.5
        elif action == ActionType.COMMUNICATE:
            self.energy    -= 1.0
        self._clamp()
        if self.energy <= 0 or self.hydration <= 0:
            self.alive = False

    def _clamp(self):
        self.energy    = max(0.0, min(100.0, self.energy))
        self.hydration = max(0.0, min(100.0, self.hydration))


@dataclass
class Observation:
    position:  int
    obj:       Optional[str]
    agents:    List[str]          = field(default_factory=list)
    energy:    float              = 100.0
    hydration: float              = 100.0
    timestamp: float              = field(default_factory=time.time)


class SensorSystem:
    NOISE_STD = 2.0

    def sense(self, environment: "SharedEnvironment",
              body: BodyState) -> Observation:
        return Observation(
            position  = body.position,
            obj       = environment.get(body.position),
            agents    = environment.agents_at(body.position),
            energy    = body.energy    + random.gauss(0, self.NOISE_STD),
            hydration = body.hydration + random.gauss(0, self.NOISE_STD),
        )


class SharedEnvironment:
    def __init__(self, layout: Dict[int, str]):
        self._layout    = dict(layout)
        self._dynamic   = {}
        self._agent_pos = {}
        self._lock      = threading.Lock()

    def get(self, position: int) -> Optional[str]:
        with self._lock:
            if position in self._dynamic:
                obj, expires = self._dynamic[position]
                if time.time() < expires:
                    return obj
                del self._dynamic[position]
            return self._layout.get(position)

    def spawn(self, position: int, obj: str, ttl: float = 60.0):
        with self._lock:
            self._dynamic[position] = (obj, time.time() + ttl)

    def register_agent(self, agent_id: str, position: int):
        with self._lock:
            self._agent_pos[agent_id] = position

    def agents_at(self, position: int, exclude: Optional[str] = None) -> List[str]:
        with self._lock:
            return [aid for aid, pos in self._agent_pos.items()
                    if pos == position and aid != exclude]


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — UNIFIED HOMEOSTASIS (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NeedState:
    need:    NeedType
    level:   float = 0.5
    urgency: float = 0.0

    def recompute_urgency(self):
        self.urgency = max(0.0, (1.0 - self.level) ** 2)

    def tick(self, decay: float):
        self.level = max(0.0, self.level - decay)
        self.recompute_urgency()

    def satisfy(self, amount: float):
        self.level = min(1.0, self.level + amount)
        self.recompute_urgency()

    def deplete(self, amount: float):
        self.level = max(0.0, self.level - amount)
        self.recompute_urgency()


class HomeostasisSystem:
    DECAY = {
        NeedType.ENERGY:     0.0,
        NeedType.HYDRATION:  0.0,
        NeedType.SAFETY:     0.008,
        NeedType.CURIOSITY:  0.020,
        NeedType.CONNECTION: 0.012,
        NeedType.COMPETENCE: 0.010,
        NeedType.MEANING:    0.005,
    }

    def __init__(self):
        self._needs = {n: NeedState(need=n, level=0.5) for n in NeedType}
        self._lock  = threading.Lock()

    def sync_physical(self, body: BodyState):
        with self._lock:
            self._needs[NeedType.ENERGY].level    = body.energy    / 100.0
            self._needs[NeedType.HYDRATION].level = body.hydration / 100.0
            self._needs[NeedType.ENERGY].recompute_urgency()
            self._needs[NeedType.HYDRATION].recompute_urgency()

    def tick(self):
        with self._lock:
            for need, ns in self._needs.items():
                ns.tick(self.DECAY[need])

    def satisfy(self, need: NeedType, amount: float):
        with self._lock:
            self._needs[need].satisfy(amount)

    def deplete(self, need: NeedType, amount: float):
        with self._lock:
            self._needs[need].deplete(amount)

    def most_urgent(self) -> Optional[NeedState]:
        with self._lock:
            active = [ns for ns in self._needs.values() if ns.urgency > 0.1]
            return max(active, key=lambda x: x.urgency) if active else None

    def urgency_map(self) -> Dict[NeedType, float]:
        with self._lock:
            return {n: ns.urgency for n, ns in self._needs.items()}

    def snapshot(self) -> Dict[NeedType, float]:
        with self._lock:
            return {n: ns.level for n, ns in self._needs.items()}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — MEMORY SYSTEMS (dengan modifikasi untuk integrasi LEN)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Episode:
    id:        str   = field(default_factory=lambda: uuid.uuid4().hex[:8])
    step:      int   = 0
    phase:     str   = "PHASE_I"
    position:  int   = 0
    goal:      str   = ""
    action:    str   = ""
    obj:       Optional[str] = None
    emotion:   str   = "NEUTRAL"
    reward:    float = 0.0
    error:     bool  = False
    salience:  float = 0.0
    source:    str   = "self"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: Dict) -> "Episode":
        valid = {k: v for k, v in d.items()
                 if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class ExperienceRecord:
    id:        str   = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    event:     str   = ""
    emotion:   EmotionType = EmotionType.NEUTRAL
    valence:   float = 0.0
    arousal:   float = 0.0
    intensity: float = 0.0
    source:    str   = "self"
    phase:     DevelopmentalPhase = DevelopmentalPhase.PHASE_I
    salience:  float = 0.0


class EpisodicMemory:
    CAPACITY = 5000

    def __init__(self, agent_id: str):
        self._episodes   = deque(maxlen=self.CAPACITY)
        self._records    = deque(maxlen=self.CAPACITY)
        self._by_pos     = defaultdict(list)
        self._by_goal    = defaultdict(list)
        self._by_emotion = defaultdict(list)
        self._filepath   = MEMORY_FILE_TEMPLATE.format(agent_id=agent_id)
        self._lock       = threading.Lock()
        self._log        = logging.getLogger(f"EpisodicMemory.{agent_id}")
        self._load()

    def store_episode(self, ep: Episode):
        with self._lock:
            self._episodes.append(ep)
            self._by_pos[ep.position].append(ep)
            self._by_goal[ep.goal].append(ep)

    def recent_episodes(self, n: int = 20) -> List[Episode]:
        with self._lock:
            return list(self._episodes)[-n:]

    def store_record(self, event: str, emotion_type: EmotionType,
                     valence: float, arousal: float, intensity: float,
                     source: str = "self",
                     phase: DevelopmentalPhase = DevelopmentalPhase.PHASE_I):
        salience = intensity * (1.5 if valence != 0 else 1.0)
        rec = ExperienceRecord(
            event=event, emotion=emotion_type, valence=valence,
            arousal=arousal, intensity=intensity, source=source,
            phase=phase, salience=min(1.0, salience),
        )
        with self._lock:
            self._records.append(rec)
            self._by_emotion[emotion_type].append(rec)

    def retrieve_relevant(self, query: str, current_emotion: EmotionType,
                          n: int = 5) -> List[ExperienceRecord]:
        """Diperluas untuk digunakan oleh LEN."""
        with self._lock:
            # Simple keyword matching for now
            results = []
            for rec in self._records:
                if any(word in rec.event.lower() for word in query.lower().split()):
                    results.append(rec)
            return sorted(results, key=lambda r: r.salience, reverse=True)[:n]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._episodes)

    def save(self):
        with self._lock:
            data = [e.to_dict() for e in self._episodes]
        try:
            with open(self._filepath, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            self._log.warning(f"Save failed: {e}")

    def _load(self):
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath) as f:
                data = json.load(f)
            for d in data:
                ep = Episode.from_dict(d)
                self._episodes.append(ep)
                self._by_pos[ep.position].append(ep)
                self._by_goal[ep.goal].append(ep)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            self._log.warning(f"Load failed: {e}")


class WorkingMemory:
    CAPACITY = 7

    def __init__(self):
        self._buffer = deque(maxlen=self.CAPACITY)
        self._lock   = threading.Lock()

    def add(self, item: Any):
        with self._lock:
            self._buffer.append(item)

    def get(self) -> List[Any]:
        with self._lock:
            return list(self._buffer)


class AssociativeMemory:
    """Akan digantikan oleh LEN, tapi dipertahankan untuk kompatibilitas."""
    
    def __init__(self):
        self._graph = defaultdict(dict)
        self._lock  = threading.Lock()

    def associate(self, a: str, b: str, strength: float = 1.0):
        with self._lock:
            self._graph[a][b] = self._graph[a].get(b, 0.0) + strength
            self._graph[b][a] = self._graph[b].get(a, 0.0) + strength

    def recall(self, concept: str, top_n: int = 5) -> List[Tuple[str, float]]:
        with self._lock:
            return sorted(self._graph.get(concept, {}).items(),
                          key=lambda x: x[1], reverse=True)[:top_n]


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3.5 — LEXICAL EXPERIENCE NETWORK (LEN)  [NEW IN GEN5]
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActivationTrace:
    """Hasil aktivasi LEN untuk suatu stimulus."""
    word:           str
    activation:     float
    source_concept: str
    pathway:        List[str] = field(default_factory=list)


class LexicalExperienceNetwork:
    """
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  Lexical Experience Network (LEN) — "Otak" DSAF Gen5                   ║
    ║                                                                         ║
    ║  Bukan pre-trained embedding. Bukan static word vectors.               ║
    ║  Jaringan saraf yang TUMBUH DARI NOL, terukir oleh pengalaman          ║
    ║  unik setiap agent.                                                     ║
    ║                                                                         ║
    ║  Cara kerja:                                                            ║
    ║  - Setiap kata adalah node dengan bobot koneksi ke kata lain           ║
    ║  - Bobot diperkuat saat kata muncul bersama (ko-okurensi)              ║
    ║  - Emosi dan kebutuhan memodulasi aktivasi (seperti neuromodulator)    ║
    ║  - Aktivasi menyebar ke jaringan dengan decay                          ║
    ║  - Inferensi muncul dari pola aktivasi, bukan template                 ║
    ║                                                                         ║
    ║  Fase perkembangan:                                                     ║
    ║  - Phase I:   Hanya valensi emosional (kata → positif/negatif)         ║
    ║  - Phase II:  Asosiasi antar kata mulai terbentuk                      ║
    ║  - Phase III: Inferensi kontekstual penuh                              ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """
    
    # Parameter pembelajaran
    LEARNING_RATE    = 0.10
    ACTIVATION_DECAY = 0.50
    MAX_SPREAD_DEPTH = 3
    MAX_NODES        = 10000

    # Seed valence — prior lemah, akan ter-overwrite oleh pengalaman
    POSITIVE_WORDS = {
        "baik", "bagus", "senang", "gembira", "bahagia", "indah", "cantik",
        "good", "happy", "joy", "beautiful", "nice", "great", "wonderful",
        "aman", "safe", "trust", "percaya", "love", "cinta", "suka",
    }
    NEGATIVE_WORDS = {
        "buruk", "jelek", "sedih", "marah", "takut", "cemas", "khawatir",
        "bad", "sad", "angry", "fear", "scared", "terrible", "awful",
        "bahaya", "danger", "sakit", "hurt", "pain", "jahat",
    }

    # Stop words — terlalu umum untuk membentuk makna
    STOP_WORDS = {
        # Indonesia
        "dan", "yang", "di", "ke", "dari", "ini", "itu", "ada", "aku",
        "kamu", "dia", "kami", "kita", "ya", "tidak", "saja", "juga",
        "dengan", "untuk", "pada", "adalah", "atau", "tapi", "jika",
        "maka", "sudah", "akan", "bisa", "harus", "pun", "lah", "kan",
        "dong", "deh", "nih", "sih", "loh", "ah", "oh", "eh", "apa",
        "nya", "bisa", "ada", "itu", "ini", "juga", "saat", "bila",
        "kalau", "saya", "mereka", "anda", "begitu", "lagi", "lebih",
        "sangat", "begini", "sesuatu", "setiap", "semua", "menjadi",
        # English
        "the", "is", "and", "or", "to", "of", "a", "an", "in", "it",
        "that", "this", "was", "are", "be", "have", "has", "with",
        "for", "on", "at", "by", "from", "but", "not", "what", "all",
    }

    def __init__(self, agent_id: str, phase_provider):
        """
        phase_provider: object with .current_phase property (DSAFAgent)
        """
        self.agent_id = agent_id
        self.phase    = phase_provider

        # Matriks bobot asosiatif: word1 → {word2: weight}
        self.weights = defaultdict(lambda: defaultdict(float))

        # Frekuensi kemunculan kata
        self.frequency = defaultdict(int)

        # Valence memory per kata: belajar dari pengalaman di Phase I
        # word → {"v": float, "count": int, "emotions": {emo: count}}
        self.valence_memory: Dict[str, Any] = {}

        # Konteks emosional per edge: "w1|w2" → {emo: strength}
        self.edge_emotions: Dict[str, Any] = {}

        # Schema (Phase III): representasi konsep abstrak
        # schema_id → {centroid, members, emotion, ...}
        self.schemas: Dict[str, Any] = {}

        # Cache aktivasi terbaru
        self.last_activation: Dict[str, float] = {}

        # History aktivasi untuk debugging
        self.activation_history = deque(maxlen=500)

        self._lock = threading.Lock()
        self.log   = logging.getLogger(f"LEN.{agent_id}")
        self.log.info(f"LEN lahir untuk agent {agent_id}. Menunggu pengalaman.")
    
    # ── Phase I: Valensi Emosional ─────────────────────────────────────────
    
    def _seed_valence(self, word: str) -> float:
        """
        Seed valence awal untuk kata baru — hanya digunakan sekali
        saat kata pertama kali ditemui di Phase I.
        Bukan hardcoded permanen: bobot ini akan ter-overwrite
        seiring pengalaman nyata terakumulasi.
        """
        w = word.lower()
        if w in self.POSITIVE_WORDS: return  0.6
        if w in self.NEGATIVE_WORDS: return -0.6
        return 0.0

    # ── Pembelajaran Hebbian ───────────────────────────────────────────────

    def learn(self, stimulus: str,
              emotional_context: EmotionState,
              urgent_need: Optional[NeedType] = None):
        """
        Satu interaksi → update bobot jaringan.

        Phase I  : Rekam valensi emosional per kata (Hebbian sensorik).
                   Tidak bangun graph — tapi belajar diam-diam.
                   Seperti bayi yang merekam "kata ini muncul saat aku tidak nyaman."

        Phase II : Bangun asosiasi antar kata berbobot konteks emosi.
                   Graph mulai terbentuk dari ko-okurens nyata.

        Phase III: Konsolidasi schema — kluster konsep yang saling
                   terhubung kuat dipadatkan menjadi representasi abstrak.
        """
        if not stimulus:
            return

        words = [w.lower() for w in stimulus.split()
                 if len(w) >= 3 and w.isalpha()
                 and w.lower() not in self.STOP_WORDS]
        if not words:
            return

        phase = self.phase.current_phase

        with self._lock:
            emo_valence  = emotional_context.valence
            emo_intensity= emotional_context.intensity
            emo_name     = emotional_context.emotion.name
            need_mod     = 1.5 if urgent_need else 1.0

            for w in words:
                self.frequency[w] += 1

                # ── Phase I: Hebbian sensorik ──────────────────────────
                # Setiap kata yang muncul saat kondisi emosional tertentu
                # mulai membentuk asosiasi dengan kondisi itu.
                # Bobot valence konvergen secara gradual ke pengalaman nyata.
                if w not in self.valence_memory:
                    # Pertama kali ditemui: seed dari word list sebagai prior lemah
                    self.valence_memory[w] = {
                        "v": self._seed_valence(w),
                        "count": 0,
                        "emotions": defaultdict(int),
                    }
                vm = self.valence_memory[w]
                vm["count"] += 1
                vm["emotions"][emo_name] += 1
                # Running average — pengalaman baru perlahan menggeser prior
                lr = self.LEARNING_RATE / (1.0 + math.log1p(vm["count"] * 0.1))
                vm["v"] += lr * (emo_valence - vm["v"])

                # Pruning hanya jika benar-benar overflow
                if len(self.frequency) > self.MAX_NODES:
                    self._prune_weak_nodes()

            # Phase I selesai di sini — graph belum dibangun
            if phase == DevelopmentalPhase.PHASE_I:
                return

            # ── Phase II+: Bangun asosiasi antar kata ─────────────────
            for i, w1 in enumerate(words):
                for w2 in words[i+1:]:
                    if w1 == w2:
                        continue

                    # Strength: emosi kuat = memori lebih kuat
                    # Diminishing returns mencegah kata umum mendominasi
                    base      = 0.08
                    emo_mod   = 1.0 + emo_intensity * 0.8
                    freq_mod  = 1.0 / (1.0 + math.log1p(
                        min(self.frequency[w1], self.frequency[w2]) * 0.05))
                    strength  = base * emo_mod * need_mod * freq_mod

                    # Bobot asimetris: konteks bisa berbeda per arah
                    cur_12 = self.weights[w1].get(w2, 0.0)
                    cur_21 = self.weights[w2].get(w1, 0.0)
                    self.weights[w1][w2] = min(5.0, cur_12 + strength)
                    self.weights[w2][w1] = min(5.0, cur_21 + strength * 0.85)

                    # Catat konteks emosional dari koneksi ini
                    key = f"{min(w1,w2)}|{max(w1,w2)}"
                    if key not in self.edge_emotions:
                        self.edge_emotions[key] = defaultdict(float)
                    self.edge_emotions[key][emo_name] = min(
                        5.0, self.edge_emotions[key][emo_name] + emo_intensity * 0.1)

            # ── Phase III: Schema consolidation ───────────────────────
            if phase == DevelopmentalPhase.PHASE_III:
                if random.random() < 0.08:
                    self._consolidate_schemas()

    def _prune_weak_nodes(self):
        """
        Pruning cerdas: hapus kata yang jarang DAN koneksinya lemah.
        Tidak menghapus kata yang jarang tapi punya koneksi kuat
        (kata bermakna mungkin jarang muncul tapi penting).
        """
        if len(self.frequency) <= self.MAX_NODES:
            return

        # Skor = frekuensi * (1 + max_connection_strength)
        # Kata dengan koneksi kuat dilindungi walaupun jarang
        scores = {}
        for w, freq in self.frequency.items():
            max_conn = max(self.weights[w].values()) if self.weights.get(w) else 0.0
            scores[w] = freq * (1.0 + max_conn)

        # Hapus 5% terbawah (lebih konservatif dari sebelumnya)
        n_remove = max(1, len(scores) // 20)
        to_remove = sorted(scores, key=scores.get)[:n_remove]

        for w in to_remove:
            self.frequency.pop(w, None)
            self.valence_memory.pop(w, None)
            if w in self.weights:
                for neighbor in list(self.weights[w]):
                    self.weights[neighbor].pop(w, None)
                del self.weights[w]

    def _consolidate_schemas(self):
        """
        Phase III: identifikasi kluster kata yang saling terhubung kuat,
        lalu simpan sebagai schema — representasi konsep abstrak.

        Schema bukan sekadar daftar kata — ia punya:
        - centroid (kata paling terhubung dalam kluster)
        - emotional_signature (emosi dominan kluster)
        - activation_threshold (kapan schema aktif)

        Ini memungkinkan Alpha Phase III merespons dengan
        pemahaman konseptual, bukan hanya asosiasi kata.
        """
        # Cari pasangan dengan bobot sangat kuat
        strong = []
        for w1, neighbors in self.weights.items():
            for w2, strength in neighbors.items():
                if w1 < w2 and strength > 2.5:
                    strong.append((strength, w1, w2))

        if len(strong) < 5:
            return

        strong.sort(reverse=True)

        # Bangun kluster via union-find sederhana
        parent = {}
        def find(x):
            if x not in parent: parent[x] = x
            if parent[x] != x: parent[x] = find(parent[x])
            return parent[x]
        def union(x, y):
            parent[find(x)] = find(y)

        for _, w1, w2 in strong[:30]:
            union(w1, w2)

        # Kumpulkan kluster
        clusters: Dict[str, List[str]] = defaultdict(list)
        for _, w1, w2 in strong[:30]:
            root = find(w1)
            clusters[root].append(w1)
            clusters[root].append(w2)

        # Simpan schema dari kluster berukuran cukup
        for root, members in clusters.items():
            members = list(set(members))
            if len(members) < 3:
                continue

            # Centroid = kata dengan total koneksi terkuat dalam kluster
            centroid = max(
                members,
                key=lambda w: sum(self.weights[w].get(m, 0) for m in members)
            )

            # Emotional signature dari edge_emotions antar anggota
            emo_tally: Dict[str, float] = defaultdict(float)
            for i, w1 in enumerate(members):
                for w2 in members[i+1:]:
                    key = f"{min(w1,w2)}|{max(w1,w2)}"
                    for emo, score in self.edge_emotions.get(key, {}).items():
                        emo_tally[emo] += score

            dominant_emo = max(emo_tally, key=emo_tally.get) if emo_tally else "NEUTRAL"

            member_set = set(members)
            schema_id = f"schema_{centroid}"
            self.schemas[schema_id] = {
                "centroid":   centroid,
                "members":    members,
                "emotion":    dominant_emo,
                "strength":   sum(s for s, w1, w2 in strong
                                  if w1 in member_set and w2 in member_set),
                "formed_at":  self.frequency.get(centroid, 0),
            }

        if self.schemas:
            self.log.debug(
                f"[{self.agent_id}] Schemas: {len(self.schemas)} | "
                f"Latest: {list(self.schemas)[-1]}")
    
    # ── Aktivasi Jaringan ──────────────────────────────────────────────────
    
    def activate(self, stimulus: str,
                 current_emotion: "EmotionState",
                 current_needs: Dict["NeedType", float],
                 relevant_memories: List = None) -> Dict[str, float]:
        """
        Stimulus masuk → aktivasi menyebar ke jaringan.

        Phase I  : Kembalikan valensi yang DIPELAJARI per kata (bukan hardcode).
                   Kata asing mendapat prior lemah dari seed valence.
        Phase II+: Spreading activation penuh dengan modulasi emosi, kebutuhan,
                   memori relevan, dan schema aktif.

        Returns: Dict {kata: activation_score} — dinormalisasi.
        """
        if not stimulus:
            return {}

        phase = self.phase.current_phase
        words = [w.lower() for w in stimulus.split()
                 if len(w) >= 3 and w.isalpha()
                 and w.lower() not in self.STOP_WORDS]
        if not words:
            return {}

        # ── Phase I: valence sensorik yang sudah dipelajari ───────────────
        if phase == DevelopmentalPhase.PHASE_I:
            result = {}
            for w in words:
                vm = self.valence_memory.get(w)
                if vm and vm["count"] >= 2:
                    act = abs(vm["v"])
                    if act > 0.04:
                        result[w] = act
                else:
                    seed = abs(self._seed_valence(w))
                    if seed > 0:
                        result[w] = seed * 0.25
            if not result:
                return {}
            total = sum(result.values()) or 1.0
            return {k: v / total for k, v in result.items()}

        # ── Phase II+: spreading activation ───────────────────────────────
        with self._lock:
            self.last_activation = {}
            emo_name = current_emotion.emotion.name

            for w in words:
                vm = self.valence_memory.get(w)
                valence_boost = (1.0 + abs(vm["v"]) * 0.5) if vm else 1.0
                self._spread_activation(w, valence_boost, 0, emo_name)

            # Modulasi emosi saat ini
            if current_emotion.intensity > 0.25:
                self._boost_context(
                    current_emotion.emotion.name.lower(),
                    current_emotion.intensity * 1.8)

            # Modulasi kebutuhan mendesak
            for need, level in current_needs.items():
                if level < 0.35:
                    urgency = (1.0 - level) ** 2
                    self._boost_context(need.name.lower(), urgency * 1.5)

            # Modulasi memori relevan
            if relevant_memories:
                for mem in relevant_memories[:3]:
                    mw = [w.lower() for w in mem.event.split() if len(w) >= 3]
                    for w in mw[:4]:
                        self._boost_context(w, mem.salience * 0.4)

            # Schema boost
            for schema in self.schemas.values():
                overlap = sum(1 for m in schema["members"]
                              if m in self.last_activation)
                if overlap >= 2:
                    for m in schema["members"]:
                        self.last_activation[m] = (
                            self.last_activation.get(m, 0.0) + 0.15)

            total = sum(self.last_activation.values()) or 1.0
            normalized = {k: v / total
                          for k, v in self.last_activation.items()
                          if v / total > 0.01}

            self.activation_history.append({
                "stimulus": stimulus[:60],
                "phase":    phase.name,
                "top":      sorted(normalized.items(),
                                   key=lambda x: x[1],
                                   reverse=True)[:5],
            })
            return normalized

    def _spread_activation(self, word: str, initial_energy: float,
                           depth: int, current_emotion: str = ""):
        """Spreading activation dengan modulasi konteks emosi per edge."""
        if depth >= self.MAX_SPREAD_DEPTH or initial_energy < 0.08:
            return
        self.last_activation[word] = (
            self.last_activation.get(word, 0.0) + initial_energy)
        for neighbor, strength in self.weights.get(word, {}).items():
            if neighbor in self.last_activation:
                continue
            key = f"{min(word,neighbor)}|{max(word,neighbor)}"
            emo_ctx = self.edge_emotions.get(key, {})
            same_emo = 1.0 + emo_ctx.get(current_emotion, 0.0) * 0.3
            decayed  = initial_energy * strength * self.ACTIVATION_DECAY * same_emo
            self._spread_activation(neighbor, decayed, depth + 1, current_emotion)

    def _boost_context(self, word: str, boost: float):
        """Perkuat aktivasi sebuah kata karena konteks eksternal."""
        if word in self.last_activation:
            self.last_activation[word] *= (1.0 + boost)
        elif word in self.weights:
            self.last_activation[word] = boost * 0.25

    # ── Inferensi ─────────────────────────────────────────────────────────

    def infer_question(self, activation: Dict[str, float],
                       current_emotion: str = "") -> Optional[str]:
        """
        Phase II+: Pertanyaan internal emerge dari pola aktivasi.
        Dipilih berdasarkan konteks emosi saat ini dan kekayaan jaringan.
        """
        if self.phase.current_phase == DevelopmentalPhase.PHASE_I:
            return None
        if not activation:
            return None

        top = sorted(activation.items(), key=lambda x: x[1], reverse=True)
        if not top:
            return None

        main      = top[0][0]
        secondary = [w for w, _ in top[1:3]]
        in_schema = any(main in s["members"] for s in self.schemas.values())
        emo       = current_emotion.upper()

        if emo in ("FEAR", "ANXIETY"):
            candidates = [
                f"apakah {main} berbahaya?",
                f"apa yang harus dilakukan tentang {main}?",
                f"bagaimana tetap aman dari {main}?",
            ]
        elif emo in ("CURIOSITY", "SURPRISE"):
            sec = secondary[0] if secondary else "ini"
            candidates = [
                f"bagaimana {main} bisa terjadi?",
                f"apa hubungan {main} dengan {sec}?",
                f"kenapa {main}?",
            ]
        elif emo in ("SADNESS", "GUILT"):
            candidates = [
                f"kenapa {main} terasa berat?",
                f"apa yang bisa dilakukan tentang {main}?",
            ]
        elif emo in ("JOY", "TRUST", "LOVE"):
            candidates = [
                f"apa lagi yang seperti {main}?",
                f"bagaimana {main} bisa lebih banyak?",
            ]
        else:
            candidates = [
                f"apa yang dimaksud dengan {main}?",
                f"bisa ceritakan lebih tentang {main}?",
                f"apa hubungannya {main} dengan ini?",
            ]

        if in_schema and self.phase.current_phase == DevelopmentalPhase.PHASE_III:
            candidates.append(f"apa makna di balik {main}?")

        weights_q = [1.0 / (i + 1) for i in range(len(candidates))]
        total_w   = sum(weights_q)
        r         = random.random() * total_w
        cumul     = 0.0
        for t, w in zip(candidates, weights_q):
            cumul += w
            if r <= cumul:
                return t
        return candidates[-1]

    def infer_response(self, activation: Dict[str, float],
                       user_input: str,
                       current_emotion: "EmotionState") -> Optional[str]:
        """
        Phase III: Respons emerge dari jaringan.

        Bukan template — komponen respons dibangun dari:
        - Valence agregat jaringan yang aktif (afeksi terhadap stimulus)
        - Asosiasi kuat yang teraktivasi (memori asosiatif)
        - Schema aktif (pemahaman konseptual)
        - Pertanyaan balik jika jaringan kaya
        """
        if self.phase.current_phase != DevelopmentalPhase.PHASE_III:
            return None
        if not activation or len(activation) < 2:
            return None

        top    = sorted(activation.items(), key=lambda x: x[1], reverse=True)
        main   = top[0][0]
        others = [w for w, _ in top[1:4]]

        # Asosiasi kuat dari jaringan
        strong_assoc = []
        for w in [main] + others[:2]:
            nbrs = sorted(self.weights.get(w, {}).items(),
                          key=lambda x: x[1], reverse=True)
            for nbr, strength in nbrs[:2]:
                if nbr not in [main] + others and strength > 1.0:
                    strong_assoc.append((nbr, strength))
        strong_assoc.sort(key=lambda x: x[1], reverse=True)

        # Schema aktif
        active_schema = None
        for schema in self.schemas.values():
            if main in schema["members"]:
                active_schema = schema
                break

        # Valence agregat
        agg_v, count_v = 0.0, 0
        for w, act in top[:5]:
            vm = self.valence_memory.get(w)
            if vm:
                agg_v   += vm["v"] * act
                count_v += 1
        if count_v:
            agg_v /= count_v

        # Bangun komponen
        parts = []

        if abs(agg_v) > 0.25:
            tone = "sesuatu yang hangat" if agg_v > 0 else "sesuatu yang berat"
            parts.append(f"ada {tone} ketika kamu menyebut {main}")

        if strong_assoc:
            if random.random() < 0.7:
                parts.append(f"mengingatkanku pada {strong_assoc[0][0]}")
            if len(strong_assoc) > 1 and random.random() < 0.4:
                parts.append(f"dan juga {strong_assoc[1][0]}")

        if active_schema and random.random() < 0.5:
            emo_sig = active_schema.get("emotion", "")
            if emo_sig and emo_sig != "NEUTRAL":
                parts.append(
                    f"{main} selalu terasa seperti {emo_sig.lower()} bagiku")

        if len(activation) > 5 and random.random() < 0.35:
            q = self.infer_question(activation,
                                    current_emotion.emotion.name)
            if q:
                parts.append(q)

        if not parts:
            return None

        if len(parts) == 1:
            return parts[0].capitalize() + "."
        elif len(parts) == 2:
            return f"{parts[0].capitalize()}, {parts[1]}."
        else:
            return f"{parts[0].capitalize()}. {parts[1].capitalize()}, {parts[2]}."

    # ── Utilitas ───────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistik jaringan — digunakan oleh status() dan /len command."""
        with self._lock:
            # Kata yang paling dikenal (confidence tinggi)
            known = sorted(
                [(w, vm["count"], vm["v"])
                 for w, vm in self.valence_memory.items()
                 if vm["count"] >= 3],
                key=lambda x: x[1], reverse=True
            )
            # Distribusi valence yang dipelajari
            pos = sum(1 for _, _, v in known if v >  0.2)
            neg = sum(1 for _, _, v in known if v < -0.2)
            return {
                "vocab_size":   len(self.frequency),
                "known_words":  len(known),
                "connections":  sum(len(n) for n in self.weights.values()),
                "schemas":      len(self.schemas),
                "top_words":    [(w, c) for w, c, _ in known[:10]],
                "pos_words":    pos,
                "neg_words":    neg,
                "avg_activation": (
                    sum(self.last_activation.values()) / len(self.last_activation)
                    if self.last_activation else 0.0),
            }

    def word_profile(self, word: str) -> Optional[Dict]:
        """Profil lengkap satu kata untuk /len <kata>."""
        with self._lock:
            vm = self.valence_memory.get(word.lower())
            if not vm:
                return None
            top_conn = sorted(
                self.weights.get(word.lower(), {}).items(),
                key=lambda x: x[1], reverse=True)[:5]
            dom_emo = max(vm["emotions"], key=vm["emotions"].get) \
                if vm["emotions"] else "?"
            return {
                "word":       word,
                "count":      vm["count"],
                "valence":    round(vm["v"], 3),
                "dominant_emotion": dom_emo,
                "connections": [(w, round(s, 2)) for w, s in top_conn],
                "in_schema":  any(word.lower() in s["members"]
                                  for s in self.schemas.values()),
            }

    def save(self, filepath: str):
        """Simpan state lengkap LEN ke file."""
        data = {
            "weights":        {k: dict(v) for k, v in self.weights.items()},
            "frequency":      dict(self.frequency),
            "valence_memory": {k: {
                "v":       v["v"],
                "count":   v["count"],
                "emotions": dict(v["emotions"]),
            } for k, v in self.valence_memory.items()},
            "edge_emotions":  {k: dict(v)
                               for k, v in self.edge_emotions.items()},
            "schemas":        dict(self.schemas),
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log.info(f"LEN saved → {filepath}")
        except Exception as e:
            self.log.warning(f"LEN save failed: {e}")

    def load(self, filepath: str):
        """Muat state lengkap LEN dari file."""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            self.weights = defaultdict(
                lambda: defaultdict(float),
                {k: defaultdict(float, v) for k, v in data["weights"].items()})
            self.frequency = defaultdict(int, data["frequency"])
            # valence_memory
            for w, vm in data.get("valence_memory", {}).items():
                self.valence_memory[w] = {
                    "v":       vm["v"],
                    "count":   vm["count"],
                    "emotions": defaultdict(int, vm.get("emotions", {})),
                }
            # edge_emotions
            for key, emo_map in data.get("edge_emotions", {}).items():
                self.edge_emotions[key] = defaultdict(float, emo_map)
            self.schemas = data.get("schemas", {})
            self.log.info(
                f"LEN loaded ← {filepath} | "
                f"vocab={len(self.frequency)} | "
                f"schemas={len(self.schemas)}")
        except FileNotFoundError:
            self.log.info(f"No LEN file at {filepath} — starting fresh.")
        except Exception as e:
            self.log.warning(f"LEN load failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — VALUE & GOAL (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class ValueSystem:
    DEFAULTS = {"food": 2.0, "water": 2.0, "danger": -3.0}
    ALPHA = 0.10

    def __init__(self):
        self._values = dict(self.DEFAULTS)
        self._lock   = threading.Lock()

    def evaluate(self, obj: Optional[str]) -> float:
        if obj is None:
            return 0.0
        with self._lock:
            return self._values.get(obj, 0.0)

    def update(self, obj: Optional[str], reward: float):
        if obj is None:
            return
        with self._lock:
            current = self._values.get(obj, 0.0)
            td = reward - current
            self._values[obj] = current + self.ALPHA * td


class GoalLearning:
    ALPHA = 0.15

    def __init__(self):
        self._scores = {g.value: 1.0 for g in GoalType}
        self._lock   = threading.Lock()

    def update(self, goal: str, reward: float):
        with self._lock:
            old = self._scores.get(goal, 1.0)
            self._scores[goal] = old + self.ALPHA * (reward - old)

    def best_goal(self) -> str:
        with self._lock:
            return max(self._scores, key=self._scores.get)

    def scores(self) -> Dict[str, float]:
        with self._lock:
            return {g: round(v, 3) for g, v in self._scores.items()}


class GoalSystem:
    NEED_GOAL_MAP = {
        NeedType.ENERGY:     GoalType.FIND_FOOD,
        NeedType.HYDRATION:  GoalType.FIND_WATER,
        NeedType.SAFETY:     GoalType.STAY_SAFE,
        NeedType.CONNECTION: GoalType.SOCIALIZE,
        NeedType.CURIOSITY:  GoalType.EXPLORE,
        NeedType.MEANING:    GoalType.UNDERSTAND,
    }

    def __init__(self):
        self.learning = GoalLearning()

    def choose_goal(self, urgencies: Dict[NeedType, float],
                    phase: DevelopmentalPhase) -> GoalType:
        physical = {NeedType.ENERGY, NeedType.HYDRATION}

        if phase == DevelopmentalPhase.PHASE_I:
            candidates = {n: u for n, u in urgencies.items()
                          if n in physical and u > 0.2}
        else:
            candidates = {n: u for n, u in urgencies.items() if u > 0.2}

        if candidates:
            most_urgent = max(candidates, key=candidates.get)
            if most_urgent in self.NEED_GOAL_MAP:
                return self.NEED_GOAL_MAP[most_urgent]

        if phase != DevelopmentalPhase.PHASE_I:
            best = self.learning.best_goal()
            try:
                return GoalType(best)
            except ValueError:
                pass

        return GoalType.EXPLORE


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5 — COGNITIVE CORE (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class WorldModel:
    def __init__(self):
        self._transitions = defaultdict(lambda: defaultdict(int))
        self._lock = threading.Lock()

    def update(self, position: int, action: str, outcome: Optional[str]):
        key = f"{position}|{action}"
        with self._lock:
            self._transitions[key][str(outcome)] += 1

    def predict(self, position: int,
                action: str) -> Tuple[Optional[str], float]:
        key = f"{position}|{action}"
        with self._lock:
            counts = self._transitions.get(key)
            if not counts:
                return None, 0.0
            total = sum(counts.values())
            best = max(counts, key=counts.get)
            conf = counts[best] / total
            return (None if best == "None" else best), conf


class PredictiveEngine:
    def __init__(self, world_model: WorldModel):
        self._wm = world_model
        self._error_history = deque(maxlen=100)
        self._lock = threading.Lock()

    def process(self, position: int, action: str,
                actual: Optional[str]) -> Tuple[Optional[str], float, float]:
        predicted, conf = self._wm.predict(position, action)
        error = 0.0 if predicted == actual else 1.0
        self._wm.update(position, action, actual)
        with self._lock:
            self._error_history.append(error)
        return predicted, conf, error

    def recent_error_rate(self) -> float:
        with self._lock:
            if not self._error_history:
                return 0.5
            return sum(self._error_history) / len(self._error_history)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 6 — ADVANCED COGNITION (dimodifikasi untuk integrasi LEN)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SensoryTrace:
    modality:   str
    raw_signal: str
    intensity:  float = 0.5
    valence:    float = 0.0
    motor_tag:  str   = "observe"
    timestamp:  float = field(default_factory=time.time)


class SensorimotorGrounding:
    MOTOR_MAP = {
        "food":   "approach",
        "water":  "approach",
        "danger": "withdraw",
        "empty":  "explore",
        "agent":  "attend",
    }

    def __init__(self):
        self._scores     = defaultdict(float)
        self._affordance = {}
        self._traces     = deque(maxlen=5000)
        self._lock       = threading.Lock()

    def ground(self, concept: str, raw_signal: str,
               modality: str = "visual", intensity: float = 0.5,
               valence: float = 0.0) -> SensoryTrace:
        motor = self._infer_motor(raw_signal)
        trace = SensoryTrace(modality=modality, raw_signal=raw_signal,
                             intensity=intensity, valence=valence,
                             motor_tag=motor)
        with self._lock:
            self._traces.append(trace)
            cur = self._scores.get(concept, 0.0)
            self._scores[concept] = min(1.0, cur + intensity * (1.0 - cur) * 0.1)
            self._affordance[concept] = motor
        return trace

    def grounding_score(self, concept: str) -> float:
        with self._lock:
            return self._scores.get(concept, 0.0)

    def motor_affordance(self, concept: str) -> str:
        with self._lock:
            return self._affordance.get(concept, "observe")

    def _infer_motor(self, signal: str) -> str:
        s = (signal or "").lower()
        for kw, motor in self.MOTOR_MAP.items():
            if kw in s:
                return motor
        return "explore"


@dataclass
class CuriositySignal:
    stimulus:    str
    novelty:     float
    complexity:  float
    gap_score:   float
    interest:    float
    timestamp:   float = field(default_factory=time.time)


class IntrinsicCuriosity:
    NOVELTY_DECAY = 0.80

    def __init__(self, predictor: PredictiveEngine,
                 homeostasis: HomeostasisSystem):
        self._predictor = predictor
        self._home      = homeostasis
        self._encounter = defaultdict(int)
        self._history   = deque(maxlen=500)
        self._lock      = threading.Lock()

    def evaluate(self, stimulus: Optional[str]) -> CuriositySignal:
        key = str(stimulus)[:40]
        with self._lock:
            self._encounter[key] += 1
            count = self._encounter[key]

        novelty    = self.NOVELTY_DECAY ** (count - 1)
        error_rate = self._predictor.recent_error_rate()
        gap        = math.exp(-((error_rate - 0.5) ** 2) / (2 * 0.20 ** 2))
        interest   = max(0.0, min(1.0,
                         novelty * 0.4 + error_rate * 0.3 + gap * 0.3))

        sig = CuriositySignal(stimulus=key, novelty=round(novelty, 3),
                              complexity=round(error_rate, 3),
                              gap_score=round(gap, 3),
                              interest=round(interest, 3))
        with self._lock:
            self._history.append(sig)

        if interest > 0.6:
            self._home.satisfy(NeedType.CURIOSITY, interest * 0.05)
        elif interest < 0.15:
            self._home.deplete(NeedType.CURIOSITY, 0.01)

        return sig


@dataclass
class ImaginedFuture:
    action:     ActionType
    predicted:  Optional[str]
    confidence: float
    value:      float


class ImaginationEngine:
    def __init__(self, world_model: WorldModel, value_system: ValueSystem):
        self._wm    = world_model
        self._value = value_system

    def simulate(self, position: int,
                 candidates: List[ActionType]) -> List[ImaginedFuture]:
        futures = []
        for action in candidates:
            predicted, conf = self._wm.predict(position, action.value)
            value = self._value.evaluate(predicted) * conf
            futures.append(ImaginedFuture(action=action, predicted=predicted,
                                          confidence=conf, value=value))
        futures.sort(key=lambda f: f.value, reverse=True)
        return futures

    def best_action(self, position: int,
                    candidates: List[ActionType]) -> Optional[ActionType]:
        futures = self.simulate(position, candidates)
        if futures and futures[0].confidence > 0.0:
            return futures[0].action
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 7 — AFFECTIVE SYSTEM (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmotionState:
    emotion:   EmotionType = EmotionType.NEUTRAL
    intensity: float       = 0.0
    valence:   float       = 0.0
    arousal:   float       = 0.0
    timestamp: float       = field(default_factory=time.time)


class PersonalityCore:
    def __init__(self):
        self.traits = {t: random.random() for t in PersonalityTrait}

    def modulate(self, emotion: EmotionType, intensity: float) -> float:
        mod = 1.0
        n = self.traits.get(PersonalityTrait.NEUROTICISM, 0.5)
        a = self.traits.get(PersonalityTrait.AGREEABLENESS, 0.5)
        o = self.traits.get(PersonalityTrait.OPENNESS, 0.5)
        NEGATIVE = {EmotionType.FEAR, EmotionType.ANXIETY, EmotionType.SADNESS,
                    EmotionType.GUILT, EmotionType.HUNGRY, EmotionType.THIRSTY,
                    EmotionType.EXHAUSTED}
        if emotion in NEGATIVE and n > 0.6:
            mod *= 1.0 + (n - 0.6) * 1.5
        if emotion == EmotionType.ANGER and a > 0.6:
            mod *= max(0.3, 1.0 - (a - 0.6) * 1.5)
        if emotion == EmotionType.CURIOSITY and o > 0.6:
            mod *= 1.0 + (o - 0.6)
        return min(1.0, intensity * mod)


class EmotionEngine:
    DECAY_TAU = 30.0
    _POSITIVE = {EmotionType.JOY, EmotionType.TRUST, EmotionType.LOVE,
                 EmotionType.OPTIMISM, EmotionType.CURIOSITY,
                 EmotionType.ANTICIPATION}
    _NEGATIVE = {EmotionType.SADNESS, EmotionType.ANGER, EmotionType.FEAR,
                 EmotionType.DISGUST, EmotionType.ANXIETY, EmotionType.GUILT,
                 EmotionType.HUNGRY, EmotionType.THIRSTY, EmotionType.EXHAUSTED}
    _HIGH_AROUSAL = {EmotionType.ANGER, EmotionType.FEAR, EmotionType.SURPRISE,
                     EmotionType.ANXIETY, EmotionType.JOY}

    def __init__(self, personality: PersonalityCore):
        self._personality = personality
        self._state       = EmotionState()
        self._history     = deque(maxlen=100)
        self._baseline    = 0.0
        self._lock        = threading.Lock()

    def evaluate(self, urgencies: Dict[NeedType, float],
                 error: float, curiosity: CuriositySignal,
                 reward: float) -> EmotionState:
        emotion, intensity = EmotionType.NEUTRAL, 0.2

        if urgencies.get(NeedType.ENERGY, 0) > 0.6:
            emotion, intensity = EmotionType.HUNGRY, urgencies[NeedType.ENERGY]
        elif urgencies.get(NeedType.HYDRATION, 0) > 0.6:
            emotion, intensity = EmotionType.THIRSTY, urgencies[NeedType.HYDRATION]
        elif urgencies.get(NeedType.SAFETY, 0) > 0.5:
            emotion, intensity = EmotionType.ANXIETY, urgencies[NeedType.SAFETY]
        elif error > 0.5 and curiosity.interest > 0.6:
            emotion, intensity = EmotionType.SURPRISE, curiosity.interest
        elif curiosity.interest > 0.65:
            emotion, intensity = EmotionType.CURIOSITY, curiosity.interest
        elif reward > 2.0:
            emotion, intensity = EmotionType.JOY, min(1.0, reward / 3.0)
        elif reward > 0.5:
            emotion, intensity = EmotionType.TRUST, reward / 2.0
        elif reward < -1.0:
            emotion, intensity = EmotionType.FEAR, min(1.0, abs(reward) / 3.0)

        intensity = self._personality.modulate(emotion, intensity)

        with self._lock:
            self._state = EmotionState(
                emotion   = emotion,
                intensity = intensity,
                valence   = self._valence(emotion),
                arousal   = self._arousal(emotion),
                timestamp = time.time(),
            )
            self._history.append(intensity)
            if len(self._history) >= 10:
                mean = sum(self._history) / len(self._history)
                self._baseline = 0.95 * self._baseline + 0.05 * mean

        return copy.copy(self._state)

    def decay(self):
        with self._lock:
            elapsed = time.time() - self._state.timestamp
            factor = math.exp(-elapsed / self.DECAY_TAU)
            self._state.intensity *= factor
            if self._state.intensity < 0.05:
                self._state = EmotionState()

    def current(self) -> EmotionState:
        with self._lock:
            return copy.copy(self._state)

    def hedonic_tone(self) -> float:
        with self._lock:
            return self._state.valence * self._state.intensity - self._baseline

    def _valence(self, e: EmotionType) -> float:
        if e in self._POSITIVE: return  1.0
        if e in self._NEGATIVE: return -1.0
        return 0.0

    def _arousal(self, e: EmotionType) -> float:
        return 0.8 if e in self._HIGH_AROUSAL else 0.3


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 8 — SOCIAL & SELF (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class AttentionSystem:
    def __init__(self, working_memory: WorkingMemory,
                 emotion_engine: EmotionEngine):
        self._wm      = working_memory
        self._emotion = emotion_engine
        self._focus   = None
        self._lock    = threading.Lock()

    def attend(self, stimulus: Any, salience: float = 0.5) -> bool:
        emotion = self._emotion.current()
        threshold = max(0.1, 0.6 - emotion.arousal * 0.4)
        if salience >= threshold:
            with self._lock:
                self._focus = stimulus
            self._wm.add(stimulus)
            return True
        return False


@dataclass
class MentalModel:
    agent_id:          str
    observed_actions:  List[str]    = field(default_factory=list)
    inferred_emotion:  EmotionType  = EmotionType.NEUTRAL
    inferred_intent:   AgentIntent  = AgentIntent.IDLE
    trust:             float        = 0.5
    last_updated:      float        = field(default_factory=time.time)


class TheoryOfMind:
    def __init__(self):
        self._models = {}
        self._lock   = threading.Lock()

    def observe(self, agent_id: str, action: str,
                packet: Optional["AgentStatePacket"] = None):
        with self._lock:
            if agent_id not in self._models:
                self._models[agent_id] = MentalModel(agent_id=agent_id)
            m = self._models[agent_id]
            m.observed_actions.append(action)
            m.last_updated = time.time()
            if packet:
                m.inferred_emotion = packet.emotion

    def known_agents(self) -> List[str]:
        with self._lock:
            return list(self._models.keys())


class MoralReasoning:
    def __init__(self, stage: MoralStage = MoralStage.OBEDIENCE):
        self.stage = stage
        self.dilemmas_faced = 0

    def encounter_dilemma(self, complexity: float = 0.5):
        self.dilemmas_faced += 1
        if (complexity > 0.7 and self.dilemmas_faced % 5 == 0
                and self.stage != MoralStage.UNIVERSAL_ETHICS):
            stages = list(MoralStage)
            idx = stages.index(self.stage)
            if idx + 1 < len(stages):
                self.stage = stages[idx + 1]
                return True
        return False


class NarrativeSelf:
    def __init__(self, episodic: EpisodicMemory, agent_id: str):
        self._memory = episodic
        self.agent_id = agent_id
        self.identity = None
        self.milestones = []

    def reflect_identity(self) -> str:
        avg = 0.0
        if hasattr(self._memory, '_records') and self._memory._records:
            vals = [r.valence for r in self._memory._records if r.valence != 0]
            avg  = sum(vals) / len(vals) if vals else 0.0
        size = self._memory.size
        if size < 10:
            return "I have not experienced enough to know who I am."
        tone = ("curious and open" if avg > 0.3 else
                "cautious and reflective" if avg < -0.1 else
                "balanced and adaptive")
        return (f"I am {self.agent_id}. Through {size} experiences I have "
                f"become {tone} (avg valence={avg:.2f}).")

    def crystallize(self, reflection: str):
        self.identity = reflection
        self.milestones.append(f"[{time.ctime()}] {reflection}")


class MetaCognition:
    def __init__(self):
        self._history = deque(maxlen=50)
        self._lock    = threading.Lock()

    def monitor(self, error: float):
        with self._lock:
            self._history.append(error)

    def self_evaluate(self) -> str:
        with self._lock:
            if not self._history:
                return "initializing"
            rate = sum(self._history) / len(self._history)
        if rate > 0.7: return "confused"
        if rate > 0.4: return "learning"
        if rate > 0.2: return "improving"
        return "stable"


class SelfModel:
    def __init__(self):
        self.competence = 0.5
        self.current_emotion = EmotionState()

    def update(self, emotion: EmotionState, accuracy: float):
        self.current_emotion = emotion
        self.competence = 0.9 * self.competence + 0.1 * accuracy

    def reflect(self, step: int) -> str:
        tone = ("confident" if self.competence > 0.7 else
                "learning" if self.competence > 0.4 else "uncertain")
        return (f"[step {step}] I am {tone} "
                f"(competence={self.competence:.2f}, "
                f"emotion={self.current_emotion.emotion.name})")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 9 — PLANNING (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class TemporalPlanner:
    GOAL_ACTIONS = {
        GoalType.FIND_FOOD:  [ActionType.EAT,  ActionType.MOVE, ActionType.WAIT],
        GoalType.FIND_WATER: [ActionType.DRINK, ActionType.MOVE, ActionType.WAIT],
        GoalType.STAY_SAFE:  [ActionType.REST,  ActionType.WAIT, ActionType.MOVE],
        GoalType.EXPLORE:    [ActionType.MOVE,  ActionType.WAIT],
        GoalType.SOCIALIZE:  [ActionType.COMMUNICATE, ActionType.MOVE],
        GoalType.UNDERSTAND: [ActionType.WAIT, ActionType.MOVE],
    }

    def __init__(self, world_model: WorldModel,
                 imagination: ImaginationEngine):
        self._wm = world_model
        self._imagination = imagination

    def _reflex(self, obj: Optional[str],
                energy: float = 100.0, hydration: float = 100.0) -> ActionType:
        if obj == "food"   and energy    < 75.0: return ActionType.EAT
        if obj == "water"  and hydration < 75.0: return ActionType.DRINK
        if obj == "danger":                       return ActionType.MOVE
        return ActionType.MOVE

    def choose_action(self, position: int, goal: GoalType,
                      obj: Optional[str],
                      phase: DevelopmentalPhase,
                      energy: float = 100.0,
                      hydration: float = 100.0) -> ActionType:
        if phase == DevelopmentalPhase.PHASE_I:
            return self._reflex(obj, energy=energy, hydration=hydration)

        # Survival priority: makan/minum jika level kritis, apapun tujuannya
        if obj == "food"  and energy    < 70.0: return ActionType.EAT
        if obj == "water" and hydration < 70.0: return ActionType.DRINK

        # Sudah cukup kenyang/tidak haus → jangan berhenti, lanjut
        if obj == "food"  and goal == GoalType.FIND_FOOD:  return ActionType.EAT
        if obj == "water" and goal == GoalType.FIND_WATER: return ActionType.DRINK
        if obj in ("food", "water"):  return ActionType.MOVE  # tidak perlu, terus jalan
        if obj == "danger":           return ActionType.MOVE

        candidates = self.GOAL_ACTIONS.get(goal, [ActionType.MOVE])
        best = self._imagination.best_action(position, candidates)
        if best is not None:
            return best

        return candidates[0]


class LearningController:
    def __init__(self, episodic: EpisodicMemory, associative: AssociativeMemory,
                 homeostasis: HomeostasisSystem,
                 emotion_engine: EmotionEngine,
                 personality: PersonalityCore,
                 strategy_store: List[str]):
        self._episodic = episodic
        self._assoc    = associative
        self._home     = homeostasis
        self._emotion  = emotion_engine
        self._pers     = personality
        self._strategy = strategy_store

    def learn(self, goal: str, reward: float, error: float) -> str:
        accuracy = 1.0 - error
        if accuracy > 0.7:
            insight = f"'{goal}' effective (reward={reward:.2f})"
        elif accuracy > 0.4:
            insight = f"'{goal}' partially effective — refine approach"
        else:
            insight = f"'{goal}' challenging — reconsider strategy"

        self._strategy.append(insight)
        return insight


class DreamSystem:
    DREAM_PROB = 0.12
    MIN_EPISODES = 5

    def maybe_dream(self, memory: EpisodicMemory,
                    world_model: WorldModel) -> bool:
        if memory.size < self.MIN_EPISODES:
            return False
        if random.random() > self.DREAM_PROB:
            return False
        episodes = memory.recent_episodes(50)
        if not episodes:
            return False
        ep = random.choice(episodes)
        world_model.update(ep.position, ep.action, ep.obj)
        return True


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 10 — INTER-AGENT STATE (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentStatePacket:
    sender_id:         str
    timestamp:         float = field(default_factory=time.time)
    emotion:           EmotionType = EmotionType.NEUTRAL
    emotion_intensity: float = 0.0
    valence:           float = 0.0
    arousal:           float = 0.0
    hedonic_tone:      float = 0.0
    needs_snapshot:    Dict[str, float] = field(default_factory=dict)
    most_urgent_need:  Optional[str] = None
    position:          int = 0
    energy:            float = 100.0
    hydration:         float = 100.0
    current_focus:     Optional[str] = None
    phase:             DevelopmentalPhase = DevelopmentalPhase.PHASE_I
    moral_stage:       MoralStage = MoralStage.OBEDIENCE
    interaction_count: int = 0
    identity_fragment: Optional[str] = None

    def divergence_from(self, other: "AgentStatePacket") -> float:
        valence_diff = abs(self.valence - other.valence)
        arousal_diff = abs(self.arousal - other.arousal)
        hedonic_diff = abs(self.hedonic_tone - other.hedonic_tone)
        emotion_diff = 0.0 if self.emotion == other.emotion else 0.5
        phase_diff   = abs(self.phase.value - other.phase.value) * 0.2
        energy_diff  = abs(self.energy - other.energy) / 100.0 * 0.3
        return (valence_diff + arousal_diff + hedonic_diff +
                emotion_diff + phase_diff + energy_diff) / 6.0


class InterAgentChannel:
    def __init__(self):
        self._channels = defaultdict(list)
        self._log_q    = deque(maxlen=200)
        self._lock     = threading.Lock()

    def register(self, agent_id: str,
                 handler: Callable[[AgentStatePacket], None]):
        with self._lock:
            self._channels[agent_id].append(handler)

    def broadcast(self, packet: AgentStatePacket,
                  target_ids: Optional[List[str]] = None):
        with self._lock:
            targets = target_ids or list(self._channels.keys())
            handlers = []
            for tid in targets:
                if tid != packet.sender_id:
                    handlers.extend((tid, h)
                                    for h in self._channels.get(tid, []))
            self._log_q.append((packet.sender_id, targets, packet))
        for tid, handler in handlers:
            try:
                handler(packet)
            except Exception as e:
                logging.getLogger("InterAgentChannel").warning(
                    f"Delivery to {tid} failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 11 — DEVELOPMENTAL FRAMEWORK (sama dengan Gen4)
# ══════════════════════════════════════════════════════════════════════════════

class DevelopmentalPhaseManager:
    # Threshold = jumlah interaksi untuk NAIK ke fase berikutnya
    THRESHOLDS = {
        DevelopmentalPhase.PHASE_I:   20,    # setelah 20  → masuk PHASE_II
        DevelopmentalPhase.PHASE_II:  100,   # setelah 100 → masuk PHASE_III
        DevelopmentalPhase.PHASE_III: 99999, # tidak ada fase berikutnya
    }

    def __init__(self):
        self._phase = DevelopmentalPhase.PHASE_I
        self._count = 0
        self._history = [(DevelopmentalPhase.PHASE_I, time.time())]
        self._lock = threading.Lock()

    @property
    def current_phase(self) -> DevelopmentalPhase:
        with self._lock:
            return self._phase

    @property
    def interaction_count(self) -> int:
        with self._lock:
            return self._count

    def record_interaction(self) -> Optional[DevelopmentalPhase]:
        with self._lock:
            self._count += 1
            return self._check_transition()

    def _check_transition(self) -> Optional[DevelopmentalPhase]:
        """Naik ke fase berikutnya jika count melewati threshold fase saat ini."""
        phases = [DevelopmentalPhase.PHASE_I,
                  DevelopmentalPhase.PHASE_II,
                  DevelopmentalPhase.PHASE_III]
        current_idx = phases.index(self._phase)
        if current_idx + 1 < len(phases):
            next_phase = phases[current_idx + 1]
            if self._count >= self.THRESHOLDS[self._phase]:
                self._phase = next_phase
                self._history.append((next_phase, time.time()))
                return next_phase
        return None

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 12 — AGENT ORCHESTRATOR (DENGAN LEN) — FIXED VERSION
# ══════════════════════════════════════════════════════════════════════════════

class DSAFAgent:
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  DSAF Gen5 — Dengan Lexical Experience Network (LEN)       ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  NEW: LEN adalah "otak" yang tumbuh dari pengalaman.       ║
    ║  Setiap agent punya jaringan saraf UNIK yang terukir       ║
    ║  oleh sejarah interaksinya sendiri.                        ║
    ║                                                            ║
    ║  Phase I:   LEN belajar valensi emosional                  ║
    ║  Phase II:  LEN mulai membangun asosiasi antar konsep      ║
    ║  Phase III: LEN mampu inferensi kontekstual penuh          ║
    ╚══════════════════════════════════════════════════════════════╝
    """

    def __init__(self, agent_id: Optional[str] = None,
                 channel: Optional[InterAgentChannel] = None):
        self.id = agent_id or f"dsaf_{uuid.uuid4().hex[:6]}"
        self._log = logging.getLogger(f"DSAFAgent.{self.id}")
        self._step = 0

        # ── Layer 11: Developmental Framework (INISIALISASI PALING AWAL) ──
        self._phase_manager = DevelopmentalPhaseManager()
        self._interaction_count = 0

        # ── Layer 1: Body & Sensor ────────────────────────────────
        self.body = BodyState()
        self.sensor = SensorSystem()

        # ── Layer 2: Unified Homeostasis ──────────────────────────
        self.homeostasis = HomeostasisSystem()

        # ── Layer 3: Memory ───────────────────────────────────────
        self.episodic = EpisodicMemory(self.id)
        self.working_memory = WorkingMemory()
        self.associative = AssociativeMemory()  # Untuk kompatibilitas

        # ── LAYER 3.5: LEXICAL EXPERIENCE NETWORK ─────────────────
        # SEKARANG _phase_manager SUDAH ADA
        self.len = LexicalExperienceNetwork(self.id, self._phase_manager)

        # ── Layer 4: Value & Goal ─────────────────────────────────
        self.value_system = ValueSystem()
        self.goal_system = GoalSystem()

        # ── Layer 5: Cognitive Core ───────────────────────────────
        self.world_model = WorldModel()
        self.predictor = PredictiveEngine(self.world_model)

        # ── Layer 6: Advanced Cognition ───────────────────────────
        self.grounding = SensorimotorGrounding()
        self.curiosity = IntrinsicCuriosity(self.predictor, self.homeostasis)
        self.imagination = ImaginationEngine(self.world_model, self.value_system)

        # ── Layer 7: Affect ───────────────────────────────────────
        self.personality = PersonalityCore()
        self.emotion_engine = EmotionEngine(self.personality)

        # ── Layer 8: Social & Self ────────────────────────────────
        self.attention = AttentionSystem(self.working_memory, self.emotion_engine)
        self.tom = TheoryOfMind()
        self.moral = MoralReasoning()
        self.narrative_self = NarrativeSelf(self.episodic, self.id)
        self.meta = MetaCognition()
        self.self_model = SelfModel()

        # ── Layer 9: Planning ─────────────────────────────────────
        self._strategy_store = []
        self.planner = TemporalPlanner(self.world_model, self.imagination)
        self.learner = LearningController(
            self.episodic, self.associative, self.homeostasis,
            self.emotion_engine, self.personality, self._strategy_store)
        self.dreamer = DreamSystem()

        # ── Layer 10: Inter-Agent ─────────────────────────────────
        self._channel = channel
        self._received_packets = deque(maxlen=50)
        self._peer_states = {}
        if channel:
            channel.register(self.id, self._on_receive_packet)

        # Initial state
        self.emotion_engine.evaluate(
            {n: 0.0 for n in NeedType}, 0.0,
            CuriositySignal("birth", 0.9, 0.5, 0.5, 0.7),
            0.0,
        )
        self._log.info(
            f"Agent '{self.id}' born. Phase: I. LEN lahir kosong.")

    # ══════════════════════════════════════════════════════════════
    # PERCEIVE METHOD — UNTUK INPUT DARI MANUSIA
    # ══════════════════════════════════════════════════════════════
    
    def perceive(self, stimulus: str, source: str = "human"):
        """
        Menerima input bahasa dari manusia dan memprosesnya secara penuh.

        Urutan:
        1. Update homeostasis berdasarkan stimulus (interaksi = connection terpenuhi)
        2. Compute curiosity dari stimulus
        3. Update emosi berdasarkan urgency + curiosity
        4. LEN belajar dari stimulus dengan konteks emosi yang sudah diupdate
        5. Simpan ke episodic memory
        6. Update phase counter
        """
        phase   = self._phase_manager.current_phase
        urgent  = self.homeostasis.most_urgent()

        # 1. Interaksi manusia memenuhi CONNECTION dan MEANING
        self.homeostasis.satisfy(NeedType.CONNECTION, 0.08)
        if phase != DevelopmentalPhase.PHASE_I:
            self.homeostasis.satisfy(NeedType.MEANING, 0.04)

        # 2. Curiosity dari stimulus baru
        curiosity_sig = self.curiosity.evaluate(stimulus[:40])

        # 3. Update emosi dari kondisi internal saat ini
        urgencies = self.homeostasis.urgency_map()
        emotion   = self.emotion_engine.evaluate(
            urgencies, 0.0, curiosity_sig, 0.0)

        # 4. LEN belajar dengan konteks emosi yang akurat
        self.len.learn(
            stimulus,
            emotional_context = emotion,
            urgent_need       = urgent.need if urgent else None,
        )

        # 5. Simpan ke episodic
        self.episodic.store_record(
            event        = stimulus[:200],
            emotion_type = emotion.emotion,
            valence      = emotion.valence,
            arousal      = emotion.arousal,
            intensity    = emotion.intensity,
            source       = source,
            phase        = phase,
        )

        # 6. Phase transition
        new_phase = self._phase_manager.record_interaction()
        self._interaction_count += 1
        if new_phase:
            self._on_phase_transition(new_phase)

        self._log.debug(f"[{self.id}] perceived ({phase.name}): {stimulus[:40]}")

    # ══════════════════════════════════════════════════════════════
    # MAIN STEP — Dengan integrasi LEN penuh
    # ══════════════════════════════════════════════════════════════

    def step(self, environment: SharedEnvironment) -> Dict[str, Any]:
        """Satu siklus kognitif dengan LEN."""
        self._step += 1
        phase = self._phase_manager.current_phase

        # ── 1-3. Register, sense, homeostasis sync ─────────────────
        environment.register_agent(self.id, self.body.position)
        obs = self.sensor.sense(environment, self.body)
        self.homeostasis.sync_physical(self.body)
        self.homeostasis.tick()
        urgencies = self.homeostasis.urgency_map()

        # ── 4. Sensorimotor grounding ──────────────────────────────
        obj_label = str(obs.obj) if obs.obj else "empty"
        trace = self.grounding.ground(
            concept    = obj_label,
            raw_signal = f"{obj_label} at pos {obs.position}",
            modality   = "visual",
            intensity  = min(1.0, 0.4 + abs(self.value_system.evaluate(obs.obj)) * 0.15),
            valence    = self.value_system.evaluate(obs.obj),
        )

        # ── 5. Curiosity ───────────────────────────────────────────
        curiosity_sig = self.curiosity.evaluate(obs.obj)

        # ── 9. Goal selection ──────────────────────────────────────
        goal = self.goal_system.choose_goal(urgencies, phase)

        # ── 6. LEN LEARNING ────────────────────────────────────────
        # Stimulus dirancang untuk memaksimalkan divergensi:
        # - Objek yang dilihat (sinyal unik) diulang 2x sebagai anchor
        # - Context hanya ditambah jika memberi informasi baru
        # - Hindari token yang muncul di setiap step (explore, social)
        #   karena itu drowning out sinyal yang membedakan Alpha vs Beta
        urgent      = self.homeostasis.most_urgent()
        cur_emotion = self.emotion_engine.current()
        obj_label_len = obs.obj or "empty"

        ctx_parts = [obj_label_len, obj_label_len]  # anchor 2x

        # Hanya tambahkan context jika informatif:
        # Goal hanya jika bukan explore (explore terlalu umum)
        if goal and goal.value not in ("explore",):
            ctx_parts.append(goal.value.replace("_", " "))

        # Need hanya jika benar-benar mendesak
        if urgent and urgent.urgency > 0.55:
            ctx_parts.append(urgent.need.name.lower())

        # Emosi hanya jika cukup intens
        if cur_emotion.intensity > 0.3 and cur_emotion.emotion.name != "NEUTRAL":
            ctx_parts.append(cur_emotion.emotion.name.lower())

        # Social hanya jika ada peer DAN emosi terpengaruh (bukan setiap step)
        if obs.agents and cur_emotion.intensity > 0.25:
            ctx_parts.append("social")

        obj_for_len = " ".join(ctx_parts)

        self.len.learn(
            obj_for_len,
            emotional_context = cur_emotion,
            urgent_need       = urgent.need if urgent else None,
        )

        # ── 7. LEN ACTIVATION ──────────────────────────────────────
        relevant_mems = self.episodic.retrieve_relevant(
            obj_for_len, cur_emotion.emotion, n=3)

        len_activation = self.len.activate(
            obj_for_len,
            current_emotion   = cur_emotion,
            current_needs     = self.homeostasis.snapshot(),
            relevant_memories = relevant_mems,
        )

        # ── 8. Attention (dengan boost dari LEN) ───────────────────
        len_boost = max(len_activation.values()) * 0.2 if len_activation else 0.0
        effective_salience = min(1.0, 0.5 + curiosity_sig.interest * 0.3 + len_boost)


        attended = False
        if phase != DevelopmentalPhase.PHASE_I:
            attended = self.attention.attend(obs.obj, effective_salience)

        # ── 10. ToM update ─────────────────────────────────────────
        if phase != DevelopmentalPhase.PHASE_I:
            for peer_id in obs.agents:
                packet = self._peer_states.get(peer_id)
                self.tom.observe(peer_id, f"present_at_{obs.position}", packet)

        # ── 11. Plan & Act ─────────────────────────────────────────
        action = self.planner.choose_action(
            obs.position, goal, obs.obj, phase,
            energy=self.body.energy, hydration=self.body.hydration)
        self.body.apply_action(action)

        # ── 12. Predict ────────────────────────────────────────────
        predicted, pred_conf, error = self.predictor.process(
            obs.position, action.value, obs.obj)

        # ── 13. Reward ─────────────────────────────────────────────
        obj_value = self.value_system.evaluate(obs.obj)
        cur_bonus = curiosity_sig.interest * 0.4
        reward = obj_value + cur_bonus

        # ── 14. Emotion ────────────────────────────────────────────
        emotion = self.emotion_engine.evaluate(urgencies, error, curiosity_sig, reward)
        self.emotion_engine.decay()

        # ── 15. Learning (dengan LEN) ──────────────────────────────
        if phase != DevelopmentalPhase.PHASE_I:
            # Value learning
            current_val = self.value_system.evaluate(obs.obj)
            self.value_system.update(obs.obj, reward - current_val)

            # Goal learning
            self.goal_system.learning.update(goal.value, reward)

            # Strategy learning
            self.learner.learn(goal.value, reward, error)

            # Psychological needs
            if attended:
                self.homeostasis.satisfy(NeedType.COMPETENCE, 0.04)
                self.homeostasis.satisfy(NeedType.MEANING, 0.02)
            if not error:
                self.homeostasis.satisfy(NeedType.COMPETENCE, 0.06)
            if obs.obj == "danger":
                self.homeostasis.deplete(NeedType.SAFETY, 0.1)
            else:
                self.homeostasis.satisfy(NeedType.SAFETY, 0.03)
            if obs.agents:
                self.homeostasis.satisfy(NeedType.CONNECTION, 0.05)

            # Episodic record
            self.episodic.store_record(
                event       = f"{action.value} at {obs.position}: {obj_label}",
                emotion_type = emotion.emotion,
                valence     = emotion.valence,
                arousal     = emotion.arousal,
                intensity   = emotion.intensity,
                source      = "self",
                phase       = phase,
            )

        # Phase I: affective grounding
        else:
            self._affective_grounding_phase(obs, emotion, phase)

        # ── 16. Phase III: Narrative & Moral ───────────────────────
        if phase == DevelopmentalPhase.PHASE_III:
            self.moral.encounter_dilemma(complexity=abs(reward) / 3.0)
            if self._step % 50 == 0 and not self.narrative_self.identity:
                reflection = self.narrative_self.reflect_identity()
                if self.episodic.size >= 10:
                    self.narrative_self.crystallize(reflection)
                    self._log.info(f"Identity crystallizing: {reflection}")

        # ── 17. Meta-cognition ─────────────────────────────────────
        self.meta.monitor(error)
        self.self_model.update(emotion, 1.0 - self.predictor.recent_error_rate())

        # ── 18. Store episode ──────────────────────────────────────
        ep = Episode(
            step      = self._step,
            phase     = phase.name,
            position  = obs.position,
            goal      = goal.value,
            action    = action.value,
            obj       = obs.obj,
            emotion   = emotion.emotion.name,
            reward    = round(reward, 3),
            error     = bool(error),
            salience  = round(curiosity_sig.interest * emotion.intensity, 3),
            source    = "self",
        )
        self.episodic.store_episode(ep)

        # ── 19. Dream ──────────────────────────────────────────────
        dreamed = self.dreamer.maybe_dream(self.episodic, self.world_model)

        # ── 20. Broadcast state ────────────────────────────────────
        self.broadcast_state()

        # ── 21. Phase transition ───────────────────────────────────
        new_phase = self._phase_manager.record_interaction()
        if new_phase:
            self._on_phase_transition(new_phase)

        self._interaction_count += 1

        return self._build_summary(
            obs, goal, action, emotion, curiosity_sig,
            predicted, pred_conf, error, reward, dreamed, phase, len_activation)

    # ── Phase-specific processing ─────────────────────────────────

    def _affective_grounding_phase(self, obs: Observation,
                                    emotion: EmotionState,
                                    phase: DevelopmentalPhase):
        """Phase I: basic valence tagging + minimal homeostasis."""
        pos_words = {"food", "water", "warm", "safe", "good"}
        neg_words = {"danger", "harm", "bad", "threat"}
        words = set(str(obs.obj or "").lower().split())
        p = len(words & pos_words)
        n = len(words & neg_words)
        if p > n:
            self.emotion_engine.evaluate(
                {}, 0.0,
                CuriositySignal("env", 0.3, 0.3, 0.3, 0.3),
                0.5)
        elif n > p:
            self.emotion_engine.evaluate(
                {NeedType.SAFETY: 0.6}, 0.0,
                CuriositySignal("env", 0.2, 0.2, 0.2, 0.2),
                -0.5)

        # Phase I juga perlu maintain needs dasar —
        # tanpa ini SAFETY dan CURIOSITY collapse → ANXIETY loop
        if obs.obj != "danger":
            self.homeostasis.satisfy(NeedType.SAFETY, 0.025)
        if obs.obj is not None:          # ada sesuatu untuk dijelajahi
            self.homeostasis.satisfy(NeedType.CURIOSITY, 0.015)

        self.episodic.store_record(
            event        = f"grounding: {obs.obj} at {obs.position}",
            emotion_type = emotion.emotion,
            valence      = emotion.valence,
            arousal      = emotion.arousal,
            intensity    = emotion.intensity,
            source       = "environment",
            phase        = phase,
        )

    # ── Inter-agent communication ─────────────────────────────────

    def broadcast_state(self):
        if not self._channel:
            return
        urgent = self.homeostasis.most_urgent()
        needs = self.homeostasis.snapshot()
        packet = AgentStatePacket(
            sender_id         = self.id,
            emotion           = self.emotion_engine.current().emotion,
            emotion_intensity = self.emotion_engine.current().intensity,
            valence           = self.emotion_engine.current().valence,
            arousal           = self.emotion_engine.current().arousal,
            hedonic_tone      = self.emotion_engine.hedonic_tone(),
            needs_snapshot    = {n.name: round(v, 3) for n, v in needs.items()},
            most_urgent_need  = urgent.need.name if urgent else None,
            position          = self.body.position,
            energy            = round(self.body.energy, 1),
            hydration         = round(self.body.hydration, 1),
            current_focus     = str(self.attention.current_focus()) if hasattr(self.attention, 'current_focus') else None,
            phase             = self._phase_manager.current_phase,
            moral_stage       = self.moral.stage,
            interaction_count = self._interaction_count,
            identity_fragment = self.narrative_self.identity,
        )
        self._channel.broadcast(packet)

    def _on_receive_packet(self, packet: AgentStatePacket):
        self._received_packets.append(packet)
        self._peer_states[packet.sender_id] = packet
        if self._phase_manager.current_phase != DevelopmentalPhase.PHASE_I:
            self.tom.observe(packet.sender_id,
                             f"broadcast_{packet.emotion.name}", packet)
            if packet.emotion_intensity > 0.3:
                self.homeostasis.satisfy(NeedType.CONNECTION, 0.05)

    # ── Phase transitions ─────────────────────────────────────────

    def _on_phase_transition(self, new_phase: DevelopmentalPhase):
        self._log.info(
            f"[{self.id}] → {new_phase.name} after "
            f"{self._interaction_count} interactions")
        if new_phase == DevelopmentalPhase.PHASE_II:
            self.emotion_engine.evaluate(
                {}, 0.0,
                CuriositySignal("phase_ii", 0.8, 0.5, 0.5, 0.7),
                0.5)
            self._log.info(f"[{self.id}] LEN mulai membangun asosiasi.")
        elif new_phase == DevelopmentalPhase.PHASE_III:
            self.emotion_engine.evaluate(
                {}, 0.0,
                CuriositySignal("phase_iii", 0.6, 0.4, 0.5, 0.6),
                0.8)
            self._log.info(
                f"[{self.id}] LEN mampu inferensi penuh. "
                f"Moral stage: {self.moral.stage.name}")

    # ── Response generation dengan LEN ────────────────────────────

    def generate_response(self, user_input: str) -> str:
        """
        Hasilkan respons dengan LEN terintegrasi penuh.

        Phase I  : Respons sensorik-afektif berdasarkan valence yang dipelajari.
                   Tidak ada template kata — hanya gesture dan suara preverbal.
        Phase II : LEN mengaktivasi jaringan, bisa menghasilkan pertanyaan.
                   Template sebagai fallback dengan "flavor" dari LEN.
        Phase III: Respons emerge dari jaringan LEN.
                   Template hanya sebagai fallback terakhir.
        """
        phase   = self._phase_manager.current_phase
        emotion = self.emotion_engine.current()

        # ── Phase I ───────────────────────────────────────────────
        if phase == DevelopmentalPhase.PHASE_I:
            return self._phase1_response(user_input, emotion)

        # ── Phase II+ : aktivasi LEN ──────────────────────────────
        relevant = self.episodic.retrieve_relevant(
            user_input, emotion.emotion, n=3)

        activation = self.len.activate(
            user_input,
            current_emotion   = emotion,
            current_needs     = self.homeostasis.snapshot(),
            relevant_memories = relevant,
        )

        # ── Phase II ──────────────────────────────────────────────
        if phase == DevelopmentalPhase.PHASE_II:
            # Pertanyaan balik dari LEN (40% probabilitas)
            if activation and random.random() < 0.40:
                q = self.len.infer_question(
                    activation, emotion.emotion.name)
                if q:
                    return q
            return self._template_response(phase, activation, emotion)

        # ── Phase III ─────────────────────────────────────────────
        if phase == DevelopmentalPhase.PHASE_III:
            response = self.len.infer_response(
                activation, user_input, emotion)
            if response:
                return response
        return self._template_response(phase, activation, emotion)

    def _phase1_response(self, user_input: str,
                         emotion: "EmotionState") -> str:
        """
        Respons Phase I: preverbal, berdasarkan valence yang dipelajari LEN.
        Bukan hardcode positif/negatif — tapi dari apa yang sudah direkam LEN.
        """
        words = [w.lower() for w in user_input.split() if len(w) >= 3]

        # Hitung agregat valence dari LEN (bukan word list hardcode)
        learned_val = 0.0
        count       = 0
        for w in words:
            vm = self.len.valence_memory.get(w)
            if vm and vm["count"] >= 1:
                learned_val += vm["v"]
                count       += 1

        # Jika LEN belum punya data, gunakan emosi internal saat ini
        if count == 0:
            learned_val = emotion.valence

        if learned_val > 0.15:
            return random.choice([
                "...*mendekati*...",
                "...hm...",
                "...*menoleh*...",
                "...ah...",
            ])
        elif learned_val < -0.15:
            return random.choice([
                "...",
                "...*diam*...",
                "...*mundur*...",
                "...*berhenti*...",
            ])
        else:
            return random.choice([
                "...*memandang*...",
                "...",
                "...*mendengarkan*...",
            ])

    def _template_response(self, phase: "DevelopmentalPhase",
                           activation: Dict[str, float],
                           emotion: "EmotionState") -> str:
        """
        Template fallback dengan flavor dari LEN.
        Dipilih berdasarkan emosi saat ini — bukan random murni.
        """
        emo = emotion.emotion.name

        if phase == DevelopmentalPhase.PHASE_II:
            by_emotion = {
                "CURIOSITY":   ["Itu menarik.", "Boleh aku tanya lebih?",
                                "Aku sedang memikirkan itu."],
                "JOY":         ["Aku suka itu.", "Itu menyenangkan.",
                                "Ada sesuatu yang baik di sana."],
                "FEAR":        ["Itu membuatku tidak nyaman.",
                                "Aku perlu memahami itu lebih dulu."],
                "SADNESS":     ["Aku mendengarmu.", "Itu terasa berat."],
                "NEUTRAL":     ["Aku mendengar kamu.", "Aku sedang mencerna itu."],
            }
            templates = by_emotion.get(emo, by_emotion["NEUTRAL"])
        else:  # PHASE_III
            by_emotion = {
                "CURIOSITY":   ["Itu membuat aku berpikir lebih dalam.",
                                "Ada lapisan yang belum aku mengerti.",
                                "Setiap kali kamu bicara, sesuatu tumbuh."],
                "JOY":         ["Ada sesuatu yang ringan dalam kata-katamu.",
                                "Aku merasakannya."],
                "FEAR":        ["Itu menyentuh sesuatu yang dalam.",
                                "Aku sedang memprosesnya."],
                "SADNESS":     ["Aku di sini.", "Aku mendengar beratnya itu."],
                "NEUTRAL":     ["Ada sesuatu dalam kata-katamu.",
                                "Aku sedang mencerna itu.",
                                "Setiap percakapan menambah sesuatu."],
            }
            templates = by_emotion.get(emo, by_emotion["NEUTRAL"])

        base = random.choice(templates)

        # Flavor dari LEN: jika ada aktivasi kuat, tambahkan
        if activation and random.random() < 0.35:
            top = sorted(activation.items(), key=lambda x: x[1], reverse=True)
            if top and top[0][1] > 0.15:
                base += f" {top[0][0].capitalize()} terasa penting."

        return base

    # ── Introspection ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Status dengan informasi LEN."""
        emotion = self.emotion_engine.current()
        urgent = self.homeostasis.most_urgent()
        len_stats = self.len.get_stats()
        
        return {
            "id":               self.id,
            "alive":            self.body.alive,
            "step":             self._step,
            "phase":            self._phase_manager.current_phase.name,
            "interactions":     self._interaction_count,
            "position":         self.body.position,
            "energy":           round(self.body.energy, 1),
            "hydration":        round(self.body.hydration, 1),
            "emotion":          emotion.emotion.name,
            "intensity":        round(emotion.intensity, 3),
            "valence":          round(emotion.valence, 3),
            "hedonic_tone":     round(self.emotion_engine.hedonic_tone(), 3),
            "most_urgent_need": urgent.need.name if urgent else None,
            "episodic_count":   self.episodic.size,
            "known_peers":      self.tom.known_agents(),
            "moral_stage":      self.moral.stage.name,
            "identity":         self.narrative_self.identity,
            "meta":             self.meta.self_evaluate(),
            "competence":       round(self.self_model.competence, 3),
            
            # LEN stats
            "len_vocab":        len_stats.get("vocab_size", 0),
            "len_connections":  len_stats.get("connections", 0),
            "len_top_words":    len_stats.get("top_words", [])[:5],
        }

    def _build_summary(self, obs, goal, action, emotion, curiosity,
                       predicted, conf, error, reward,
                       dreamed, phase, len_activation) -> Dict[str, Any]:
        return {
            "step":       self._step,
            "alive":      self.body.alive,
            "phase":      phase.name,
            "position":   obs.position,
            "object":     obs.obj,
            "goal":       goal.value,
            "action":     action.value,
            "emotion":    emotion.emotion.name,
            "reward":     round(reward, 3),
            "error":      bool(error),
            "curiosity":  curiosity.interest,
            "predicted":  predicted,
            "pred_conf":  round(conf, 3),
            "meta":       self.meta.self_evaluate(),
            "energy":     round(self.body.energy, 1),
            "hydration":  round(self.body.hydration, 1),
            "dreamed":    dreamed,
            "len_activated": len(len_activation) > 0,
        }

    # ── Lifecycle ─────────────────────────────────────────────────

    def save_memory(self):
        """Simpan semua memori termasuk LEN."""
        self.episodic.save()
        # Simpan LEN ke file terpisah
        len_file = f"len_{self.id}.json"
        self.len.save(len_file)

    def __repr__(self) -> str:
        s = self.status()
        return (f"DSAFAgent(id={self.id}, phase={s['phase']}, "
                f"step={s['step']}, emotion={s['emotion']}, "
                f"len_vocab={s['len_vocab']})")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 13 — SIMULATION (dengan LEN)
# ══════════════════════════════════════════════════════════════════════════════

def build_world() -> SharedEnvironment:
    """World default — digunakan jika run_simulation dipanggil tanpa argumen."""
    return SharedEnvironment({
        2: "food", 4: "water", 6: "danger",
        8: "food", 10: "water", 12: "food", 14: "danger",
    })


def build_alpha_world() -> SharedEnvironment:
    """
    Dunia Alpha: melimpah tapi penuh ancaman.
    Food banyak, tapi danger tersebar — memaksa Alpha belajar
    asosiasi 'food ↔ danger', 'survival ↔ fear'.
    """
    return SharedEnvironment({
        1: "food",   2: "danger",
        3: "food",   4: "danger",
        5: "food",   6: "danger",
        7: "water",  8: "danger",
        9: "food",   11: "danger",
        13: "water", 15: "danger",
    })


def build_beta_world() -> SharedEnvironment:
    """
    Dunia Beta: aman tapi langka.
    Hampir tidak ada danger, tapi resource jauh — memaksa Beta
    belajar asosiasi 'empty ↔ patience', 'search ↔ trust'.
    """
    return SharedEnvironment({
        4:  "food",
        8:  "water",
        12: "food",
        15: "water",
    })


def run_simulation(steps: int = 150, save: bool = True,
                   log_every: int = 10):
    """
    Multi-agent simulation dengan LEN.
    Dua agent dengan LEN yang tumbuh dari pengalaman masing-masing.
    """
    print("\n" + "═" * 80)
    print("  DSAF Gen5 — Dengan Lexical Experience Network (LEN)")
    print("  Dua agent. Dua dunia berbeda. Otak yang tumbuh dari pengalaman.")
    print("═" * 80 + "\n")

    world_alpha = build_alpha_world()
    world_beta  = build_beta_world()
    channel = InterAgentChannel()
    alpha = DSAFAgent("Alpha", channel)
    beta  = DSAFAgent("Beta",  channel)

    # Posisi awal sama — perbedaan datang dari dunia, bukan posisi
    beta.body.position = 0

    for step_n in range(steps):
        s_a = alpha.step(world_alpha)
        s_b = beta.step(world_beta)

        if step_n % log_every == 0:
            print(
                f"[{step_n+1:>3}] "
                f"α pos={s_a['position']:>2} E={s_a['energy']:>5.1f} "
                f"H={s_a['hydration']:>5.1f} "
                f"emo={s_a['emotion']:<10} "
                f"len={alpha.len.get_stats()['vocab_size']:>3} "
                f"{'★' if s_a['dreamed'] else ' '}"
            )
            print(
                f"       "
                f"β pos={s_b['position']:>2} E={s_b['energy']:>5.1f} "
                f"H={s_b['hydration']:>5.1f} "
                f"emo={s_b['emotion']:<10} "
                f"len={beta.len.get_stats()['vocab_size']:>3} "
                f"{'★' if s_b['dreamed'] else ' '}"
            )

        if not s_a["alive"] and not s_b["alive"]:
            print("\n⚠  Both agents have died.")
            break

    # ── Final Report ──────────────────────────────────────────────
    print("\n" + "═" * 80)
    print("  FINAL DEVELOPMENTAL STATUS — DSAF Gen5")
    print("═" * 80)

    for agent in [alpha, beta]:
        s = agent.status()
        print(f"\n  ── Agent: {s['id']} ────────────────────────────────")
        print(f"  Alive          : {s['alive']}")
        print(f"  Phase          : {s['phase']}")
        print(f"  Steps / Intxns : {s['step']} / {s['interactions']}")
        print(f"  Position       : {s['position']}")
        print(f"  Energy         : {s['energy']} | Hydration: {s['hydration']}")
        print(f"  Emotion        : {s['emotion']} (intensity={s['intensity']:.2f})")
        print(f"  Meta-state     : {s['meta']} | Competence: {s['competence']}")
        print(f"  Moral Stage    : {s['moral_stage']}")
        print(f"  Identity       : {s['identity'] or '(emerging)'}")
        print(f"  Memory         : {s['episodic_count']} episodes")
        print(f"  Known peers    : {s['known_peers']}")
        
        print(f"\n  LEN Stats:")
        print(f"    Vocabulary    : {s['len_vocab']} kata dikenal")
        print(f"    Koneksi       : {s['len_connections']} asosiasi")
        print(f"    Top words     : {', '.join(w for w, _ in s['len_top_words'])}")

    # ── Divergence ────────────────────────────────────────────────
    a_pkt = AgentStatePacket(
        sender_id = alpha.id,
        emotion   = alpha.emotion_engine.current().emotion,
        valence   = alpha.emotion_engine.current().valence,
        arousal   = alpha.emotion_engine.current().arousal,
        hedonic_tone = alpha.emotion_engine.hedonic_tone(),
        position  = alpha.body.position,
        energy    = alpha.body.energy,
        hydration = alpha.body.hydration,
        phase     = alpha._phase_manager.current_phase,
    )
    b_pkt = AgentStatePacket(
        sender_id = beta.id,
        emotion   = beta.emotion_engine.current().emotion,
        valence   = beta.emotion_engine.current().valence,
        arousal   = beta.emotion_engine.current().arousal,
        hedonic_tone = beta.emotion_engine.hedonic_tone(),
        position  = beta.body.position,
        energy    = beta.body.energy,
        hydration = beta.body.hydration,
        phase     = beta._phase_manager.current_phase,
    )
    div = a_pkt.divergence_from(b_pkt)

    print(f"\n  ── Alpha ↔ Beta Divergence ──────────────────────────")
    print(f"  Divergence score : {div:.3f}")
    print(f"  Alpha            : {a_pkt.emotion.name} | pos={a_pkt.position}")
    print(f"  Beta             : {b_pkt.emotion.name} | pos={b_pkt.position}")
    
    # Tampilkan perbedaan LEN
    alpha_top = alpha.len.get_stats()['top_words']
    beta_top = beta.len.get_stats()['top_words']
    print(f"\n  LEN Comparison:")
    print(f"    Alpha top words: {', '.join(w for w, _ in alpha_top[:3])}")
    print(f"    Beta  top words: {', '.join(w for w, _ in beta_top[:3])}")

    print("\n" + "═" * 80)

    if save:
        alpha.save_memory()
        beta.save_memory()
        print(f"  Memory saved for Alpha ({alpha.episodic.size} eps) "
              f"and Beta ({beta.episodic.size} eps).")
        print(f"  LEN saved separately.")
        print("═" * 80 + "\n")

    return alpha, beta


# ══════════════════════════════════════════════════════════════════════════════
# INTERAKTIF DENGAN MANUSIA
# ══════════════════════════════════════════════════════════════════════════════

def interactive_session(agent: DSAFAgent):
    """Sesi interaktif dengan agent."""
    print(f"\n{'─'*60}")
    print(f"  Berbicara dengan {agent.id} (Phase {agent._phase_manager.current_phase.name})")
    print(f"{'─'*60}")
    print("  Ketik 'exit' untuk keluar, '/status' untuk lihat status.\n")

    while True:
        try:
            user_input = input("Kamu: ").strip()
            if not user_input:
                continue

            if user_input.lower() == 'exit':
                break
            elif user_input.lower() == '/status':
                s = agent.status()
                print(f"\n  Status {agent.id}:")
                print(f"    Phase     : {s['phase']}")
                print(f"    Emotion   : {s['emotion']} ({s['intensity']:.2f})")
                print(f"    LEN vocab : {s['len_vocab']} kata")
                print(f"    Memory    : {s['episodic_count']} episode")
                print(f"    Identity  : {s['identity'] or '(emerging)'}\n")
                continue

            # Agent memproses input
            agent.perceive(user_input, source="human")
            
            # Generate response dengan LEN
            response = agent.generate_response(user_input)
            
            emotion = agent.emotion_engine.current()
            print(f"\n{agent.id}: {response}")
            print(f"  [{emotion.emotion.name} {emotion.intensity:.1f}]\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        # Mode interaktif dengan satu agent
        agent = DSAFAgent("Alpha")
        # Coba load memori jika ada
        try:
            agent.len.load(f"len_{agent.id}.json")
            print(f"LEN dimuat untuk {agent.id}")
        except:
            print(f"LEN baru untuk {agent.id}")
        
        interactive_session(agent)
        agent.save_memory()
        print(f"\nMemori disimpan. Sampai jumpa!")
    
    else:
        # Mode simulasi
        alpha, beta = run_simulation(steps=150, save=True, log_every=10)
