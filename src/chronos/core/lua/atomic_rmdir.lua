-- atomic_rmdir.lua
-- KEYS: []
-- ARGV: [parent_inode, filename]

local parent_inode = ARGV[1]
local filename = ARGV[2]

-- Validate relationships atomically with the mutation.
if filename == '.' or filename == '..' or filename == '' or string.find(filename, '/', 1, true) then
    return redis.error_reply('EINVAL')
end
local parent_mode = tonumber(redis.call('HGET', 'fs:inode:' .. parent_inode, 'mode') or '0')
if bit.band(parent_mode, 61440) ~= 16384 then
    return redis.error_reply('ENOTDIR')
end
-- 1. Get the inode of the directory
local inode = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if not inode then
    return -1 -- ENOENT
end

local mode = tonumber(redis.call('HGET', 'fs:inode:' .. inode, 'mode') or '0')
if bit.band(mode, 61440) ~= 16384 then
    return redis.error_reply('ENOTDIR')
end
-- 2. Check if directory is empty (only has . and ..)
local count = redis.call('ZCARD', 'fs:dir:' .. inode)
if count > 2 then
    return -2 -- ENOTEMPTY
end

-- 3. Remove it from parent directory
redis.call('ZREM', 'fs:dir:' .. parent_inode, filename)

-- 4. Delete the directory inode and its contents
redis.call('DEL', 'fs:inode:' .. inode)
redis.call('DEL', 'fs:dir:' .. inode)

redis.call('HINCRBY', 'fs:inode:' .. parent_inode, 'nlink', -1)
local now = redis.call('TIME')[1]
redis.call('HSET', 'fs:inode:' .. parent_inode, 'mtime', now, 'ctime', now)
return inode
