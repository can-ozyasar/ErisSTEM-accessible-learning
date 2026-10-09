"""Authored learning modules with separate instruction and assessment contracts.

No source extraction, generative marking, diagnosis, or student answer storage.
The server owns solutions and hints. Local progress is a learning aid, not grades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .set_practice import (
    EXERCISES as SET_EXERCISES,
)
from .set_practice import (
    AnswerSubmission,
)
from .set_practice import (
    Exercise as SetExercise,
)
from .set_practice import (
    check_answer as check_set_answer,
)
from .set_practice import (
    public_bank as public_set_bank,
)

Stage = Literal["baseline", "guided", "transfer", "review"]


class Choice(BaseModel):
    id: str
    text: str


class Lesson(BaseModel):
    id: str
    title: str
    short_description: str
    detailed_description: list[str]
    exploration: list[str]
    limitation: str


class LearningExercise(BaseModel):
    id: str
    stage: Stage
    topic: str
    question: str
    spoken_question: str
    answer_kind: Literal["set", "choice"]
    answer_format: str
    lesson_id: str
    choices: list[Choice] = Field(default_factory=list)


class ModuleSummary(BaseModel):
    id: str
    version: str
    title: str
    goal: str
    materials: str
    quality_status: Literal["unreviewed", "expert-approved", "published"] = "unreviewed"


class LearningModule(ModuleSummary):
    provenance: str
    review_delay_hours: int = 24
    lessons: list[Lesson]
    exercises: list[LearningExercise]


class LearningFeedback(BaseModel):
    correct: bool
    valid: bool
    message: str
    error_kind: Literal["format", "answer_mismatch"] | None = None
    hint: str | None = None


@dataclass(frozen=True)
class ChoiceTask:
    public: LearningExercise
    correct_choice: str
    hint: str


def choice_task(
    task_id: str, stage: Stage, topic: str, question: str,
    options: tuple[str, ...], correct_index: int, hint: str = "",
    lesson_id: str = "main",
) -> ChoiceTask:
    return ChoiceTask(
        public=LearningExercise(
            id=task_id, stage=stage, topic=topic, question=question,
            spoken_question=question, answer_kind="choice",
            answer_format="Bir yanıt seçin.", lesson_id=lesson_id,
            choices=[Choice(id=f"option-{i + 1}", text=text) for i, text in enumerate(options)],
        ),
        correct_choice=f"option-{correct_index + 1}", hint=hint,
    )


SET_LESSONS = [
    Lesson(
        id="union", title="Birleşim: en az birinde olanlar",
        short_description="A birleşim B, A'da veya B'de bulunan bütün elemanları içerir.",
        detailed_description=[
            "Küme, elemanların bir arada ele alındığı bir topluluktur. Bir elemanı tekrar yazmak yeni bir eleman eklemez.",
            "Birleşimde her eleman için şu soruyu sorun: A'da veya B'de bulunuyor mu? En az birinde varsa sonuçta yer alır.",
            "İki kümede ortak olan eleman da sonuçta yer alır, fakat yalnız bir kez yazılır. Çember çizmek zorunlu değildir.",
        ],
        exploration=[
            "İsterseniz iki kısa liste oluşturun: birinde sevdiğiniz yiyecekler, diğerinde bir arkadaşınızın sevdikleri olsun.",
            "Listelerden en az birinde bulunan adları yeni bir listede toplayın. Ortak adları bir kez yazın.",
        ],
        limitation="Listeler yalnız küme ilişkisini örnekler. Liste sırası ve fiziksel yerleşim birleşimin özelliği değildir.",
    ),
    Lesson(
        id="intersection", title="Kesişim: ikisinde de olanlar",
        short_description="A kesişim B, hem A'da hem B'de bulunan ortak elemanları içerir.",
        detailed_description=[
            "Bir elemanın yalnız bir kümede bulunması kesişime girmesi için yeterli değildir.",
            "A'nın her elemanı için B'de de bulunup bulunmadığını kontrol edin. İkisinde de varsa ortak elemandır.",
            "Ortak eleman yoksa sonuç boş kümedir. Boş küme, sıfır sayısını içeren kümeyle aynı değildir.",
        ],
        exploration=[
            "İsterseniz iki metin veya sesli listede bulunan aynı adları belirleyin.",
            "Birinci listede olup ikinci listede olmayan bir adı da bulun. Bunun neden ortak olmadığını açıklayın.",
        ],
        limitation="Liste örneği ilişkiyi gösterir; kesişim yalnız sayı kümelerinde kullanılmaz.",
    ),
    Lesson(
        id="difference", title="Fark: A'da olup B'de olmayanlar",
        short_description="A fark B, A'nın elemanlarından B'de bulunmayanları içerir.",
        detailed_description=[
            "Önce A'yı başlangıç kümesi olarak ele alın. A'nın dışındaki elemanlar sonuçta yer alamaz.",
            "A'daki bir eleman B'de de varsa sonuçtan çıkarılır; B'de yoksa korunur.",
            "A fark B ile B fark A genellikle farklıdır. İşlemde kümelerin sırası önemlidir.",
        ],
        exploration=[
            "İsterseniz yapılacak işler ve tamamlanmış işler için iki liste oluşturun.",
            "Yapılacaklar listesinde olup tamamlanmışlar listesinde bulunmayan işleri belirleyin.",
        ],
        limitation="Bu örnek küme farkını anlatır; sayısal çıkarma işlemiyle aynı işlem değildir.",
    ),
]

SET_BASELINE = (
    choice_task("union-baseline", "baseline", "En az birinde bulunma",
                "A listesinde çay ve süt, B listesinde süt ve su var. En az bir listede bulunanların hepsi hangisidir?",
                ("Yalnız süt", "Çay, süt ve su", "Yalnız çay"), 1, lesson_id="union"),
    choice_task("intersection-baseline", "baseline", "Ortak olma",
                "Bir listede ekmek ve su, diğerinde su ve elma var. İki listede de bulunan hangisidir?",
                ("Su", "Ekmek ve elma", "Ekmek, su ve elma"), 0, lesson_id="intersection"),
    choice_task("difference-baseline", "baseline", "Yalnız ilk listede olma",
                "Yapılacak işler: okuma ve yazma. Tamamlanmış iş: okuma. Yapılacaklarda olup tamamlanmışlarda olmayan hangisidir?",
                ("Okuma", "Okuma ve yazma", "Yazma"), 2, lesson_id="difference"),
)
SET_REVIEW = (
    SetExercise("union-review", "transfer", "Birleşim", (-2, 3, 7), (3, 8), "union", ("", "", "")),
    SetExercise("intersection-review", "transfer", "Kesişim", (-1, 4, 8), (4, 8, 9), "intersection", ("", "", "")),
    SetExercise("difference-review", "transfer", "Fark", (2, 6, 9), (6, 10), "difference", ("", "", "")),
)

CIRCLE_LESSON = Lesson(
    id="main", title="Çemberi tanıtan ilişki",
    short_description="Çember, düzlemde sabit bir noktaya eşit uzaklıktaki noktaların oluşturduğu şekildir. Sabit nokta merkezdir.",
    detailed_description=[
        "Merkezden çemberin her noktasına olan uzaklık aynıdır. Bu uzaklığa yarıçap denir. Merkez çemberin üzerinde değildir.",
        "Çember yalnız çevreyi anlatır; daire iç bölgeyi de içerir. Çemberin köşesi yoktur ve çevresi kapalıdır.",
        "Köşesiz ve kapalı olmak tek başına yeterli değildir. Uzun ve kısa eksenleri farklı bir elips de köşesiz ve kapalıdır, ama çember değildir.",
        "Şeklin büyüklüğü ve düzlemdeki yeri değişebilir. Çemberi belirleyen ilişki, merkeze eşit uzaklıktır.",
    ],
    exploration=[
        "İsterseniz bir halka veya sabitlenmiş kabartma çevre çizgisi kullanın. Materyal yoksa tanım ve ilişki sorularıyla devam edebilirsiniz.",
        "Çevreyi izleyin: köşe var mı, başlangıca dönüyor musunuz? Bu özelliklerin tek başına çemberi belirlemediğini düşünün.",
        "Merkezi işaretlenmiş uygun bir çizim varsa merkezden birkaç çevre noktasına uzaklığı karşılaştırın. Merkez çevrenin parçası değildir.",
    ],
    limitation="Halkanın kalınlığı ve malzemesi modele aittir. Matematiksel çember kalın bir cisim veya küre değildir. Bu yönergeler dokunsal materyalin yerine geçmez.",
)
CIRCLE_TASKS = (
    choice_task("circle-baseline", "baseline", "Ön bilgi",
                "Çemberi belirleyen temel ilişki hangisidir?",
                ("Merkeze uzaklıkların eşit olması", "İçinin dolu olması", "Üç köşesinin olması"), 0),
    choice_task("circle-guided", "guided", "Çevre ve iç bölge",
                "Bir şeklin yalnız çevresindeki noktaları ele alıyoruz; iç bölge dahil değil. Merkeze uzaklıklar eşit. Hangi kavramı anlatıyoruz?",
                ("Küre", "Çember", "Daire ve iç bölgesi"), 1,
                "Çevreyi ve iç bölgeyi ayırın. Hangi kavram yalnız çevredeki noktaları anlatır?"),
    choice_task("circle-ellipse-guided", "guided", "Karşı örnek",
                "Bir şekil kapalı ve köşesiz. Merkezden çevreye uzaklıklar aynı değil. Bu iki özellik onu çember yapar mı?",
                ("Evet, köşesiz olması yeterli", "Evet, kapalı olması yeterli", "Hayır, uzaklık ilişkisi de gerekir"), 2,
                "Tanımdaki merkeze eşit uzaklık koşulunu kontrol edin; yalnız köşe ve kapanma özelliklerini düşünmeyin."),
    choice_task("circle-transfer", "transfer", "Yeni durumda uygulama",
                "Düzlemde bir noktaya tam 5 santimetre uzaklıktaki bütün noktaları alıyoruz. Hangi şekil oluşur?",
                ("İçi dolu bir daire", "Yarıçapı 5 santimetre olan çember", "Bir doğru parçası"), 1),
    choice_task("circle-center-transfer", "transfer", "Merkez ve çevre",
                "Yarıçapı 3 santimetre olan bir çemberin merkezi, çemberin üzerindeki noktalardan biri midir?",
                ("Hayır, merkezin kendisine uzaklığı sıfırdır", "Evet, bütün noktalar merkezdir", "Yalnız büyük çemberlerde"), 0),
    choice_task("circle-review", "review", "Gecikmeli yeni görev",
                "Bir düzlemde O noktasına tam 7 birim uzaklıktaki bütün noktalar seçiliyor. O noktası bu seçime dahil mi?",
                ("Evet, çünkü ortada", "Yalnız çizim büyükse", "Hayır, O'nun kendisine uzaklığı 7 birim değil"), 2),
    choice_task("circle-relation-review", "review", "İlişkiyi koruma",
                "Bir çemberin yeri değiştiriliyor; merkezi de aynı miktarda taşınıyor ve yarıçapı korunuyor. Hangi ilişki devam eder?",
                ("Merkezden çevreye uzaklıklar eşittir", "Merkez çevrenin parçasıdır", "İç bölge çemberin parçasıdır"), 0),
)

AIRPLANE_LESSON = Lesson(
    id="main", title="Uçak: bütün, parçalar ve ilişkiler",
    short_description="Burada yaygın bir sabit kanatlı uçak modelinin gövde, kanat ve kuyruk ilişkilerini keşfediyoruz.",
    detailed_description=[
        "Gövde, modelin önden arkaya uzanan ana bölümüdür. Burun ön tarafta, kuyruk arka taraftadır.",
        "Bu yaygın modelde iki ana kanat gövdenin iki yanına uzanır. Kuyruk bölümünde de daha küçük yüzeyler bulunabilir; her yana uzanan parça ana kanat değildir.",
        "Sağ ve sol, uçağın içindeymiş gibi burna doğru bakma yönüne göre tanımlanır. Modeli elinizde döndürmeniz uçağın kendi sağını ve solunu değiştirmez.",
        "Bu ders yerleşim ilişkilerini öğretir. Uçuş fiziği, havaalanı işlemleri ve gerçek ortamda bağımsız hareket ayrı öğrenme hedefleridir.",
    ],
    exploration=[
        "İsterseniz sivri veya hareketli parçaları olmayan bir uçak modeli kullanın. Önce bütünü, sonra burun ve kuyruğu bulun.",
        "Modelin burnunu kendinizden uzağa yöneltin. Gövdeyi önden arkaya, ardından ana kanatları gövdeden iki yana izleyin.",
        "Modeli döndürüp aynı parçaları tekrar bulun. Konumunuza göre değişen yönlerle uçağa göre tanımlanan yönleri ayırın.",
    ],
    limitation="Model küçültülmüş ve sadeleştirilmiştir; bütün uçakların kanat ve motor yerleşimleri aynı değildir. Motor sesi biçimin yerine geçmez. Bu ders yönelim ve hareket eğitimi değildir.",
)
AIRPLANE_TASKS = (
    choice_task("airplane-baseline", "baseline", "Parça ilişkisi",
                "Burun ve kuyruk, yaygın bir uçak modelinde gövdenin hangi taraflarındadır?",
                ("İkisi de önünde", "Burun önde, kuyruk arkada", "İkisi de sağında"), 1),
    choice_task("airplane-guided", "guided", "Yön referansı",
                "Uçağın kendi sağını tanımlarken hangi yönü referans alıyoruz?",
                ("Uçağın içindeymiş gibi burna doğru bakmayı", "Modeli tutan kişinin o anki sağını", "Her zaman odanın kapısını"), 0,
                "Yönü tanımlarken uçağa bağlı bir referans seçin. Modeli tutan kişinin yeri değişebilir."),
    choice_task("airplane-parts-guided", "guided", "Bütün ve parça",
                "Yaygın modelde ana kanatlar gövdeyle nasıl ilişkilidir?",
                ("Gövdenin iki yanına uzanır", "Burunla aynı parçadır", "Gövdeyle ilişkisi yoktur"), 0,
                "Önce gövdeyi önden arkaya düşünün, sonra ana kanatların gövdeye göre uzandığı yönleri ele alın."),
    choice_task("airplane-transfer", "transfer", "Yeni konum",
                "Uçak modeli masada yarım tur döndürüldü. Uçağın kendi sağı, uçağın kendi soluna dönüşür mü?",
                ("Evet, model her döndüğünde", "Hayır, uçağa bağlı yön aynı kalır", "Yalnız model küçükse"), 1),
    choice_task("airplane-sound-transfer", "transfer", "Temsil sınırı",
                "Bir motor kaydını dinlemek, bu uçakta kanatların ve motorların tam konumunu belirlemek için yeterli midir?",
                ("Evet, bütün uçaklar aynıdır", "Evet, ses bütün biçimi verir", "Hayır, yapısal bilgi veya uygun bir temsil gerekir"), 2),
    choice_task("airplane-review", "review", "Gecikmeli yeni görev",
                "Başka bir kişi uçağın önünde duruyor. Onun sağı ile uçağın kendi sağı aynı referansa mı dayanır?",
                ("Her zaman aynı referansa dayanır", "Hayır, kişi ve uçak farklı referanslardır", "Yalnız ses açıksa"), 1),
    choice_task("airplane-model-review", "review", "Modelden genelleme",
                "Bir modelin motorları kanatlarında. Bütün uçakların motorları aynı yerde olmak zorunda mı?",
                ("Hayır, uçak tasarımları farklı olabilir", "Evet, tek bir model hepsini belirler", "Yalnız modeli döndürürsek"), 0),
)

SUMMARIES = (
    ModuleSummary(id="sets", version="sets-learning-v2", title="Kümeler ve ilişkiler",
                  goal="En az birinde, ikisinde de ve yalnız ilkinde bulunmayı yeni sorularda kullanın.",
                  materials="Metin veya sesli listeler yeterli; çizim gerekmez."),
    ModuleSummary(id="circle", version="circle-learning-v1", title="Çemberi keşfet",
                  goal="Çemberi eşit uzaklık ilişkisiyle tanıyın; çevre, iç bölge ve merkezi ayırın.",
                  materials="İsteğe bağlı halka veya merkezi işaretlenmiş kabartma çizim."),
    ModuleSummary(id="airplane", version="airplane-learning-v1", title="Uçak: parçalar ve yönler",
                  goal="Bir modelde parçaların konumunu ve yön referansını anlayın.",
                  materials="İsteğe bağlı güvenli uçak modeli; model olmadan ilişki soruları kullanılabilir."),
)


def module_catalog() -> list[ModuleSummary]:
    return list(SUMMARIES)


def read_module(module_id: str) -> LearningModule | None:
    summary = next((item for item in SUMMARIES if item.id == module_id), None)
    if summary is None:
        return None
    if module_id == "sets":
        exercises = [task.public for task in SET_BASELINE]
        for public, private in zip(public_set_bank().exercises, SET_EXERCISES, strict=True):
            exercises.append(LearningExercise(
                **public.model_dump(), answer_kind="set", lesson_id=private.operation,
            ))
        for task in SET_REVIEW:
            left, right = ", ".join(map(str, task.left)), ", ".join(map(str, task.right))
            spoken = {"union": "birleşim", "intersection": "kesişim", "difference": "fark"}[task.operation]
            question = f"A kümesi: {left}. B kümesi: {right}. A {spoken} B kümesini bulun."
            exercises.append(LearningExercise(
                id=task.id, stage="review", topic=task.topic, question=question,
                spoken_question=question, answer_kind="set", lesson_id=task.operation,
                answer_format="Örnek giriş: {1, 2, 3}. Boş küme için {} veya ∅ yazın.",
            ))
        # Instruction precedes independent transfer, rather than alternating hints and tests.
        ordered = [item for stage in ("baseline", "guided", "transfer", "review")
                   for item in exercises if item.stage == stage]
        lessons = SET_LESSONS
    else:
        tasks = CIRCLE_TASKS if module_id == "circle" else AIRPLANE_TASKS
        ordered = [task.public for task in tasks]
        lessons = [CIRCLE_LESSON if module_id == "circle" else AIRPLANE_LESSON]
    return LearningModule(
        **summary.model_dump(),
        provenance="ErişSTEM için hazırlanmış sentetik öğrenme içeriği. Uzman ve kullanıcı değerlendirmesi bekliyor; resmî sınav sorusu değildir.",
        lessons=lessons, exercises=ordered,
    )


def check_module_answer(
    module_id: str, exercise_id: str, submission: AnswerSubmission,
) -> LearningFeedback | None:
    if module_id == "sets":
        set_task = next((task for task in (*SET_EXERCISES, *SET_REVIEW)
                         if task.id == exercise_id), None)
        if set_task:
            result = check_set_answer(set_task, submission)
            return LearningFeedback(
                correct=result.correct, valid=result.valid,
                message=("Doğru yanıt." if result.correct else
                         "Yanıt henüz doğru değil. İlk yanıtınız kaydedildi; sonraki göreve geçebilirsiniz."
                         if result.valid and set_task.stage == "transfer" else result.message),
                error_kind=None if result.correct else "answer_mismatch" if result.valid else "format",
                hint=result.hint,
            )
        tasks = SET_BASELINE
    elif module_id == "circle":
        tasks = CIRCLE_TASKS
    elif module_id == "airplane":
        tasks = AIRPLANE_TASKS
    else:
        return None
    task = next((item for item in tasks if item.public.id == exercise_id), None)
    if task is None:
        return None
    if submission.answer not in {option.id for option in task.public.choices}:
        return LearningFeedback(correct=False, valid=False, error_kind="format",
                                message="Sorudaki seçeneklerden birini seçin.")
    correct = submission.answer == task.correct_choice
    return LearningFeedback(
        correct=correct, valid=True,
        message="Doğru yanıt." if correct else "Yanıt henüz doğru değil. İsterseniz daha sonra yeniden çalışabilirsiniz.",
        error_kind=None if correct else "answer_mismatch",
        hint=task.hint if not correct and task.public.stage == "guided" else None,
    )
