-- atomic_mkdir.lua
-- KEYS: []
-- ARGV: [parent_inode, filename, mode, timestamp]

local parent_inode = ARGV[1]
local filename = ARGV[2]
local mode = ARGV[3]
local timestamp = ARGV[4]

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
local inode = redis.call('INCR', 'fs:next_inode')

-- 3. Create directory inode metadata
redis.call('HSET', 'fs:inode:' .. inode,
    'mode', mode,
    'uid', 0,
    'gid', 0,
    'size', 4096,
    'ctime', timestamp,
    'mtime', timestamp,
    'atime', timestamp,
    'nlink', 2
)

-- 4. Add to parent directory
redis.call('ZADD', 'fs:dir:' .. parent_inode, inode, filename)

-- 5. Initialize internal directory structure (. and ..)
redis.call('ZADD', 'fs:dir:' .. inode, inode, '.', parent_inode, '..')

redis.call('HINCRBY', 'fs:inode:' .. parent_inode, 'nlink', 1)
redis.call('HSET', 'fs:inode:' .. parent_inode, 'mtime', timestamp, 'ctime', timestamp)
return inode
