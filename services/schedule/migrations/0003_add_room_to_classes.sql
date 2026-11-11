-- Existing classes keep all their columns and get 'Main studio' as their room.
ALTER TABLE classes
    ADD room NVARCHAR(50) NOT NULL
    CONSTRAINT df_classes_room DEFAULT 'Main studio';
