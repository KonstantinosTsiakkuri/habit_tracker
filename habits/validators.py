"""
Валидаторы привычки.

Правила хранятся в одном месте и используются дважды:
- HabitSerializer.validate() — для API (значения при PATCH дополняются из instance);
- Habit.clean() — для админки и full_clean().
"""
from django.core.exceptions import ValidationError

MAX_DURATION = 120  # секунд
MIN_PERIODICITY = 1  # дней
MAX_PERIODICITY = 7  # дней


def validate_duration(value):
    """Время на выполнение: от 1 до 120 секунд."""
    if value < 1 or value > MAX_DURATION:
        raise ValidationError(f"Время выполнения должно быть от 1 до {MAX_DURATION} секунд.")


def validate_periodicity(value):
    """Периодичность: от 1 до 7 дней (реже раза в неделю нельзя)."""
    if value < MIN_PERIODICITY or value > MAX_PERIODICITY:
        raise ValidationError(
            f"Периодичность должна быть от {MIN_PERIODICITY} до {MAX_PERIODICITY} дней "
            "(привычку нельзя выполнять реже, чем раз в 7 дней)."
        )


def validate_habit_rules(*, owner_id, is_pleasant, related_habit, reward, instance=None):
    """
    Проверяет связи между полями привычки.

    Принимает УЖЕ ИТОГОВЫЕ значения полей (после слияния с instance при частичном обновлении).
    Возвращает словарь {поле: [сообщения]}; пустой словарь — ошибок нет.
    """
    errors = {}

    def add(field, message):
        errors.setdefault(field, []).append(message)

    # Нельзя одновременно вознаграждение и связанная привычка
    if reward and related_habit:
        add("related_habit", "Нельзя одновременно указывать вознаграждение и связанную привычку.")

    if related_habit is not None:
        # В связанные попадают только приятные привычки
        if not related_habit.is_pleasant:
            add("related_habit", "В связанные привычки можно выбрать только приятную привычку.")
        # Чужие привычки использовать нельзя
        if related_habit.owner_id != owner_id:
            add("related_habit", "Связанная привычка должна принадлежать тому же пользователю.")
        # Привычка не может ссылаться сама на себя
        if instance is not None and instance.pk is not None and related_habit.pk == instance.pk:
            add("related_habit", "Привычка не может быть связана сама с собой.")

    # У приятной привычки нет ни вознаграждения, ни связанной привычки
    if is_pleasant:
        if reward:
            add("reward", "У приятной привычки не может быть вознаграждения.")
        if related_habit is not None:
            add("related_habit", "У приятной привычки не может быть связанной привычки.")
    # Нельзя «снять» признак приятной, пока на привычку ссылаются другие
    elif instance is not None and instance.pk is not None and instance.dependent_habits.exists():
        add("is_pleasant", "Привычка используется как связанная у других привычек — она должна оставаться приятной.")

    return errors
