-- atomic_unlink.lua
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
-- 1. Get the inode of the file
local inode = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if not inode then
    return -1 -- ENOENT
end

local mode = tonumber(redis.call('HGET', 'fs:inode:' .. inode, 'mode') or '0')
if bit.band(mode, 61440) == 16384 then
    return redis.error_reply('EISDIR')
end
-- 2. Remove it from the parent directory
redis.call('ZREM', 'fs:dir:' .. parent_inode, filename)

-- 3. Decrement nlink
local nlink = redis.call('HINCRBY', 'fs:inode:' .. inode, 'nlink', -1)
if nlink <= 0 then
    -- It's fully detached, clean it up completely
    local content_hash = redis.call('HGET', 'fs:inode:' .. inode, 'content_hash')
    -- Blobs are shared by hash. Reclamation requires reachability accounting;
    -- unlinking one inode must never destroy another inode's bytes.
    redis.call('DEL', 'fs:inode:' .. inode)
    redis.call('DEL', 'fs:dir:' .. inode)
end

local now = redis.call('TIME')[1]
redis.call('HSET', 'fs:inode:' .. parent_inode, 'mtime', now, 'ctime', now)
return inode
