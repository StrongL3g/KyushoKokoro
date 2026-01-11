-- Создаем основной фрейм аддона
local SimpleFrames = CreateFrame("Frame", "SimpleFrames", UIParent)
SimpleFrames:RegisterEvent("PLAYER_LOGIN")
SimpleFrames:RegisterEvent("PLAYER_ENTERING_WORLD") -- Для надёжности (если PLAYER_LOGIN не хватит)
SimpleFrames:RegisterEvent("PLAYER_REGEN_DISABLED") -- Вход в бой
SimpleFrames:RegisterEvent("PLAYER_REGEN_ENABLED")  -- Выход из боя
SimpleFrames:RegisterEvent("ACTIVE_TALENT_GROUP_CHANGED")
SimpleFrames:RegisterEvent("PLAYER_TALENT_UPDATE")
SimpleFrames:RegisterEvent("UNIT_POWER_UPDATE")
SimpleFrames:RegisterEvent("UNIT_POWER_FREQUENT")
SimpleFrames:RegisterEvent("UNIT_DISPLAYPOWER")
SimpleFrames:RegisterEvent("PLAYER_TARGET_CHANGED")

-- НОВОЕ: Регистрируем события для подсчета целей
SimpleFrames:RegisterEvent("NAME_PLATE_UNIT_ADDED")
SimpleFrames:RegisterEvent("NAME_PLATE_UNIT_REMOVED")

local SPEC_COLORS = {
    -- Warrior
    [71]  = {0.78, 0.30, 0.00},  -- Arms        (тёмно-оранжевый, как меч)
    [72]  = {0.90, 0.30, 0.10},  -- Fury        (ярко-красный, как ярость)
    [73]  = {0.55, 0.55, 0.55},  -- Protection  (серебристо-стальной)

    -- Paladin
    [65]  = {0.95, 0.95, 1.00},  -- Holy        (светло-голубовато-белый, "свет")
    [66]  = {0.70, 0.15, 0.25},  -- Protection  (тёмно-бордовый, как щит)
    [70]  = {1.00, 0.50, 0.00},  -- Retribution (золотисто-оранжевый, как молот)

    -- Hunter
    [253] = {0.40, 0.80, 0.20},  -- Beast Mastery (зелёный, как зверь/природа)
    [254] = {1.00, 0.50, 0.00},  -- Marksmanship  (золотой, как выстрел/меткость)
    [255] = {0.00, 0.70, 0.40},  -- Survival      (бирюзово-зелёный, как выживание в дикой природе)

    -- Rogue
    [259] = {0.30, 0.90, 0.30},  -- Assassination (ядово-зелёный)
    [260] = {0.90, 0.80, 0.20},  -- Outlaw        (золотой, как пират)
    [261] = {0.50, 0.35, 0.85},  -- Subtlety      (фиолетовый, как тень)

    -- Priest
    [256] = {0.55, 0.85, 1.00},  -- Discipline    (голубой, как щит/дисциплина)
    [257] = {1.00, 1.00, 0.70},  -- Holy          (тёплый кремово-белый, "святость")
    [258] = {0.35, 0.20, 0.55},  -- Shadow        (тёмно-фиолетовый, как тьма)

    -- Death Knight
    [250] = {0.80, 0.10, 0.10},  -- Blood         (тёмно-красный, кровь)
    [251] = {0.50, 0.80, 1.00},  -- Frost         (ледяной голубой)
    [252] = {0.20, 0.70, 0.20},  -- Unholy        (ядово-зелёный, как чума)

    -- Shaman
    [262] = {1.00, 0.50, 0.00},  -- Elemental     (огненно-оранжевый)
    [263] = {0.00, 0.70, 0.20},  -- Enhancement   (зелёный, как духи природы)
    [264] = {0.30, 0.60, 1.00},  -- Restoration   (голубой, как исцеление)

    -- Mage
    [62]  = {0.85, 0.70, 1.00},  -- Arcane        (фиолетово-лавандовый)
    [63]  = {1.00, 0.30, 0.00},  -- Fire          (ярко-оранжевый)
    [64]  = {0.30, 0.75, 1.00},  -- Frost         (холодный голубой)

    -- Warlock
    [265] = {0.55, 0.30, 0.85},  -- Affliction    (тёмно-фиолетовый)
    [266] = {0.85, 0.30, 0.30},  -- Demonology    (тёмно-красный, как демоны)
    [267] = {0.90, 0.40, 0.00},  -- Destruction   (огненно-оранжевый)

    -- Monk
    [268] = {0.85, 0.55, 0.20},  -- Brewmaster    (коричнево-бронзовый, как пиво/броня)
    [269] = {0.20, 0.90, 0.60},  -- Mistweaver    (мягкий бирюзовый, как туман)
    [270] = {1.00, 0.85, 0.20},  -- Windwalker    (золотисто-жёлтый, как ветер/молния)

    -- Druid
    [102] = {0.95, 0.60, 0.15},  -- Balance       (золотисто-оранжевый, как луна/звёзды)
    [103] = {0.00, 0.70, 0.25},  -- Feral         (ярко-зелёный, как зверь)
    [104] = {0.60, 0.40, 0.15},  -- Guardian      (тёмно-коричневый, как медведь)
    [105] = {0.20, 0.85, 0.40},  -- Restoration   (сочный зелёный, как исцеление/листья)

    -- Demon Hunter
    [577] = {0.90, 0.10, 0.40},  -- Havoc         (ярко-розово-красный, как хаос)
    [581] = {0.55, 0.10, 0.70},  -- Vengeance     (тёмно-фиолетовый, как месть/демон)

    -- Evoker
    [578] = {1.00, 0.35, 0.00},  -- Devastation   (огненно-оранжевый, как драконий огонь)
    [579] = {0.15, 0.85, 0.65},  -- Preservation  (глубокий бирюзовый, как исцеление)
    [580] = {0.90, 0.65, 0.20},  -- Augmentation  (золотисто-янтарный, как усиление)
}

-- НОВОЕ: Таблица для хранения активных целей
SimpleFrames.activeTargets = {}

-- Функция получения цвета текущей специализации
local function GetClassSpecColor()
    local specIndex = GetSpecialization()
    if specIndex then
        local specID = select(1, GetSpecializationInfo(specIndex))
        local c = specID and SPEC_COLORS[specID]
        if c then return c[1], c[2], c[3] end
    end
    return 0.4, 0.4, 0.4
end

-- НОВАЯ ФУНКЦИЯ: Получение количества активных целей
function SimpleFrames:GetTargetCount()
    local count = 0
    for _ in pairs(self.activeTargets) do
        count = count + 1
    end
    return count
end

-- Функция для создания фреймов
function SimpleFrames:CreateFrames()
    -- Фрейм 1: готовность (например, белый угловой пиксель)
    self.frame1 = CreateFrame("Frame", nil, UIParent)
    self.frame1:SetSize(1, 1)
    self.frame1:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", 0, 0)
    local tex1 = self.frame1:CreateTexture(nil, "BACKGROUND")
    tex1:SetAllPoints()
    tex1:SetColorTexture(1, 1, 1, 1)

    -- Фрейм 2: бой (в левом верхнем углу)
    self.frame2 = CreateFrame("Frame", nil, UIParent)
    self.frame2:SetSize(1, 1)
    self.frame2:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 0, 0)
    self.tex2 = self.frame2:CreateTexture(nil, "BACKGROUND")
    self.tex2:SetAllPoints()
    self.tex2:SetColorTexture(0, 0, 0, 1)

    -- Фрейм 3: класс/спек (справа от фрейма 2)
    self.frame3 = CreateFrame("Frame", nil, UIParent)
    self.frame3:SetSize(1, 1)  -- чуть крупнее для наглядности
    self.frame3:SetPoint("LEFT", self.frame2, "RIGHT", 0, 0)  -- 2px отступ
    self.tex3 = self.frame3:CreateTexture(nil, "BACKGROUND")
    self.tex3:SetAllPoints()
    self:UpdateClassSpecColor()

	-- Фрейм 4: количество целей
    self.frame4 = CreateFrame("Frame", nil, UIParent)
    self.frame4:SetSize(1, 1)  -- чуть крупнее для наглядности
    self.frame4:SetPoint("LEFT", self.frame3, "RIGHT", 0, 0)  -- 2px отступ
    self.tex4 = self.frame4:CreateTexture(nil, "BACKGROUND")
    self.tex4:SetAllPoints()
	self.tex4:SetColorTexture(0, 0, 0, 1)

    -- Фрейм 5: чёрный фрейм подложка для бафов
    self.frame5 = CreateFrame("Frame", nil, UIParent)
    self.frame5:SetSize(230, 150)
    self.frame5:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 490, -1050)
    self.tex5 = self.frame5:CreateTexture(nil, "BACKGROUND")
    self.tex5:SetAllPoints()
    self.tex5:SetColorTexture(0, 0, 0, 1)  -- Чёрный цвет
end

-- Обновление цвета фрейма 3
function SimpleFrames:UpdateClassSpecColor()
    if not self.tex3 then return end
    local r, g, b = GetClassSpecColor()
    self.tex3:SetColorTexture(r, g, b, 1)
end

-- НОВАЯ ФУНКЦИЯ: Проверка, является ли юнит врагом
local function IsEnemyUnit(unitID)
    if not unitID then return false end

    -- Проверяем, является ли юнит врагом
    if UnitCanAttack("player", unitID) then
        return true
    end

    return false
end

-- Функция для расчета цвета на основе количества целей
function SimpleFrames:CalculateTargetColor(count)
    if count == 0 then
        return 0, 0, 0  -- черный
    end

    local red = count * 0.1  -- каждая цель = +0.1 к красному
    if red > 1 then red = 1 end  -- максимум = ярко-красный

    return red, 0, 0
end

-- Обработчик событий
SimpleFrames:SetScript("OnEvent", function(self, event, ...)
    if event == "PLAYER_LOGIN" or event == "PLAYER_ENTERING_WORLD" then
        -- PLAYER_ENTERING_WORLD гарантирует, что класс/спек уже загружены
        if not self.framesCreated then
            self:CreateFrames()
            self.framesCreated = true
        end
        self:UpdateClassSpecColor()
        -- Начальное состояние боя — лучше через событие, но на всякий:
        self.tex2:SetColorTexture(0, 0, 0, 1)  -- default: not in combat
    elseif event == "PLAYER_REGEN_DISABLED" then
        self.tex2:SetColorTexture(1, 0, 0, 1)  -- красный — в бою
    elseif event == "PLAYER_REGEN_ENABLED" then
        self.tex2:SetColorTexture(0, 0, 0, 1)  -- чёрный — вне боя

        -- НОВОЕ: Очищаем цели при выходе из боя
        self.activeTargets = {}
		self.tex4:SetColorTexture(0, 0, 0, 1)
        --print("Выход из боя. Количество целей: 0")

    elseif event == "ACTIVE_TALENT_GROUP_CHANGED" or event == "PLAYER_TALENT_UPDATE" then
        self:UpdateClassSpecColor()

    -- НОВОЕ: Обработка событий для подсчета целей
    elseif event == "NAME_PLATE_UNIT_ADDED" then
        local unitID = ...
        if unitID and IsEnemyUnit(unitID) then
            -- Добавляем цель в таблицу
            self.activeTargets[unitID] = true

            -- Получаем количество целей и выводим в print
            local count = self:GetTargetCount()
			local r, g, b = self:CalculateTargetColor(count)
			self.tex4:SetColorTexture(r, 0, 0, 1)
            --print("Добавлена цель. Количество целей: " .. r, count)
        end

    elseif event == "NAME_PLATE_UNIT_REMOVED" then
        local unitID = ...
        if unitID and self.activeTargets[unitID] then
            -- Удаляем цель из таблицы
            self.activeTargets[unitID] = nil

            -- Получаем количество целей и выводим в print
            local count = self:GetTargetCount()
			local r, g, b = self:CalculateTargetColor(count)
			self.tex4:SetColorTexture(r, 0, 0, 1)
			--print("Удалена цель. Количество целей: " .. r, count)
        end
    end
end)