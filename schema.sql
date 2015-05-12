drop table if exists stats;

create table stats (
	`id` int primary key autoincrement,
	`url` varchar 255 not null,
	`downtime` int not null
);
