-- 创建 forecast_module 表
CREATE TABLE IF NOT EXISTS `forecast_module` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '模块ID',
    `name` VARCHAR(100) NOT NULL COMMENT '预测模块名',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '模块描述',
    `mission_kind` VARCHAR(50) DEFAULT NULL COMMENT '担任的任务类型',
    `priority` INT DEFAULT NULL COMMENT '优先级',
    `module_hash` VARCHAR(64) NOT NULL COMMENT '模块标识符',
    `alive` TINYINT(1) DEFAULT 0 COMMENT '在线状态(1:在线 0:离线)',
    `session_id` VARCHAR(64) DEFAULT NULL COMMENT 'SessionId',
    `last_alive_time` DATETIME DEFAULT NULL COMMENT '最近在线时间',
    `last_login_time` DATETIME DEFAULT NULL COMMENT '最近登录时间',
    `data_requirement` JSON DEFAULT NULL COMMENT '数据要求(JSON格式)',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_module_hash` (`module_hash`),
    KEY `idx_name` (`name`),
    KEY `idx_alive` (`alive`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预测模块表';
