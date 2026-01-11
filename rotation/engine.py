# rotation/engine.py

class RotationEngine:
    def __init__(self, profile=None):
        self.profile = profile or {"rotation": []}

    def evaluate(self, player_state, target_state):
        """
        Оценивает правила ротации и возвращает действие.
        :param player_state: dict — результат player.get_state_for_evaluation()
        :param target_state: dict — результат target.get_state_for_evaluation()
        :return: str или None — имя способности (spell name)
        """
        # Объединяем состояния
        context = {**player_state, **target_state}

        print(f"🔍 Rotation context: {context}")

        for rule in self.profile.get("rotation", []):
            spell = rule["spell"]
            condition = rule["condition"]
            if self._evaluate_condition(condition, context):
                return spell
        return None

    def _evaluate_condition(self, condition, context):
        """Безопасная оценка условия с плоскими переменными."""
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except Exception as e:
            print(f"⚠️ Rotation condition error: {condition} → {e}")
            return False