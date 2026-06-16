-- 1. Создание таблицы сущностей (Детали / Сборки / Изделия)
CREATE TABLE item (
    id BIGINT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    designation TEXT,          -- Обозначение по ГОСТ 2.201 (децимальный номер)
    name TEXT NOT NULL,        -- Наименование изделия/детали
    inventory_id INTEGER UNIQUE,      -- Инвентарный номер (Инв.№)
    file_data BYTEA,
    PRIMARY KEY (id, version)
);

-- 2. Создание таблицы связей (Дерево применяемости)
CREATE TABLE parent_child (
    parent_id BIGINT NOT NULL,
    child_id BIGINT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3. Наполнение тестовыми данными
-- Обозначение (designation) и наименование (name) — разные поля.
-- Структура соответствует example_document.pdf (изделие ЭМЦША.116.31100.000.00).

INSERT INTO item (id, version, designation, name, inventory_id) VALUES
(1, 1, 'АБВГ.471535.024', 'МПК', 117706),
(2, 1, 'АБВГ.471535.024ЛУ', 'Лист утверждения', 117707),
(3, 1, 'АБВГ.471535.024ГЧ', 'Габаритный чертеж', 117708),
(3, 2, 'АБВГ.471535.024ГЧ', 'Габаритный чертеж', 117749),
(4, 1, 'АБВГ.471535.024Е1', 'Схема деления структурная', 117709),
(5, 1, 'АБВГ.471535.024ВП', 'Ведомость покупных изделий', 117710),
(6, 1, 'АБВГ.471535.024ВП-ЛУ', 'Ведомость покупных изделий. Лист утверждения', 117711),
(7, 1, 'АБВГ.464311.004', 'Блок', 117712),
(8, 1, 'АБВГ.464311.004-01СБ', 'Сборочный чертеж', 117713),     -- № изменения 1
(8, 2, 'АБВГ.464311.004-01СБ', 'Сборочный чертеж', 117750), -- № изменения 2!
(9, 1, 'АБВГ.754529.008', 'Крышка', 117752),
(10, 1, 'АБВГ.755471.061', 'Клавиша', 117760);
-- Заполняем структуру связей (parent_child).
-- Связи привязаны к ID элемента (не к версии).
INSERT INTO parent_child (parent_id, child_id, is_primary) VALUES
(1, 2, TRUE),
(1, 3, TRUE),
(1, 4, TRUE),
(1, 5, TRUE),
(1, 6, TRUE),
(1, 7, TRUE),
(1, 10, TRUE),
(7, 8, TRUE),
(7, 9, TRUE),

(7, 10, FALSE);  -- Блок коммутации -> Мобильное средство ВТ (заимствование!)

-- ============================================================
-- Триггер: запрет циклов в дереве parent → child
-- ============================================================
CREATE OR REPLACE FUNCTION check_parent_child_no_cycle() RETURNS TRIGGER AS
$$
DECLARE
    max_depth INT;
    has_cycle BOOLEAN;
BEGIN
    -- Рекурсивно ищем путь от нового child_id обратно к parent_id
    -- Если нашли — значит добавление создаёт цикл
    WITH RECURSIVE ancestors AS (
        -- Начинаем с родителей нового элемента (те, кто уже является parent для child_id)
        SELECT pc.parent_id AS node_id, 1 AS depth
        FROM parent_child pc
        WHERE pc.child_id = NEW.parent_id

        UNION ALL

        -- Поднимаемся вверх по дереву
        SELECT pc.parent_id, a.depth + 1
        FROM parent_child pc
        JOIN ancestors a ON pc.child_id = a.node_id
        WHERE a.depth < 100
    )
    SELECT COALESCE(MAX(depth), 0),
           BOOL_OR(node_id = NEW.child_id)
    INTO max_depth, has_cycle
    FROM ancestors;

    IF has_cycle THEN
        RAISE EXCEPTION 'Обнаружен цикл: связь % → % создаёт цикл в дереве',
            NEW.parent_id, NEW.child_id;
    END IF;

    IF max_depth >= 100 THEN
        RAISE EXCEPTION 'Превышена максимальная глубина дерева (100): связь % → %',
            NEW.parent_id, NEW.child_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_parent_child_no_cycle
    BEFORE INSERT OR UPDATE
    ON parent_child
    FOR EACH ROW
EXECUTE FUNCTION check_parent_child_no_cycle();

-- ============================================================
-- Ограничение: у ребёнка может быть только ОДИН первичный Перв. примен.
-- (is_primary = TRUE). Заимствования (is_primary = FALSE) не ограничены.
-- ============================================================
CREATE UNIQUE INDEX idx_one_primary_parent
    ON parent_child (child_id)
    WHERE is_primary = TRUE;

-- ============================================================
-- Связи parent_child не привязаны к версии:
-- одно и то же изделие (id) имеет одинаковые связи для всех версий.
-- Поэтому parent_id и child_id ссылаются на id (без version).
-- ============================================================
ALTER TABLE parent_child
    ADD CONSTRAINT fk_parent_child_parent
        FOREIGN KEY (parent_id) REFERENCES item (id)
        ON DELETE CASCADE,
    ADD CONSTRAINT fk_parent_child_child
        FOREIGN KEY (child_id) REFERENCES item (id)
        ON DELETE CASCADE;
