-- atomic_create.lua
-- KEYS: []
-- ARGV: [parent_inode, filename, mode, timestamp, uid, gid, journal...]

local parent_inode = ARGV[1]
local filename = ARGV[2]
local mode = ARGV[3]
local timestamp = ARGV[4]
local uid = ARGV[5]
local gid = ARGV[6]

-- Validate relationships atomically with the mutation.
if filename == '.' or filename == '..' or filename == '' or string.find(filename, '/', 1, true) then
    return redis.error_reply('EINVAL')
end
local parent_mode = tonumber(redis.call('HGET', 'fs:inode:' .. parent_inode, 'mode') or '0')
if bit.band(parent_mode, 61440) ~= 16384 then
    return redis.error_reply('ENOTDIR')
end
-- 1. Check if file already exists in parent directory
local existing_file = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if existing_file then
    return -1  -- EEXIST
end

if tonumber(redis.call('GET', 'fs:next_inode') or '0') >= 10000 then
    return redis.error_reply('ENOSPC')
end
-- 2. Allocate new inode
local inode_counter = redis.call('INCR', 'fs:next_inode')

-- 3. Create inode metadata
-- Default umask logic or passed mode should handle permissions
-- uid/gid 0 (root) by default
redis.call('HSET', 'fs:inode:' .. inode_counter,
    'mode', mode,
    'uid', uid,
    'gid', gid,
    'size', 0,
    'ctime', timestamp,
    'mtime', timestamp,
    'atime', timestamp,
    'nlink', 1
)

-- 4. Add to parent directory (Score=Inode, Member=Filename)
-- Note: Redis Sorted Sets treat Score as floating point.
-- If inode exceeds 2^53, precision loss occurs. 
-- However, we store Inode as Score effectively.
-- Wait, ZADD stores Member (string) and Score (float).
-- We want to lookup Inode by Filename.
-- So we probably want: ZADD fs:dir:<parent> <inode> <filename>
-- Then ZSCORE <filename> returns <inode>.
redis.call('ZADD', 'fs:dir:' .. parent_inode, inode_counter, filename)

-- 5. Increase nlink for parent if this is a directory (mkdir)
-- Not handled here as we don't know if 'mode' implies directory effectively enough without bitwise ops
-- Caller should handle .. link or we do it if we passed a flag.
-- For now, generic create.

redis.call('HSET', 'fs:inode:' .. parent_inode, 'mtime', timestamp, 'ctime', timestamp)
if ARGV[7] and ARGV[7] ~= '' then
    redis.call('HSET', 'fs:mutation:' .. ARGV[7],
        'operation_id', ARGV[7], 'operation', ARGV[8], 'path', ARGV[9],
        'inode', inode_counter, 'command_id', ARGV[10], 'origin', ARGV[11],
        'completed_at', timestamp, 'schema_version', 1, 'session_id', ARGV[12] or '')
    redis.call('ZADD', 'fs:mutation_journal', timestamp, ARGV[7])
end
return inode_counter
