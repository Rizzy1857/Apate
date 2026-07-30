-- atomic_unlink.lua
-- KEYS: []
-- ARGV: [parent_inode, filename]

local parent_inode = ARGV[1]
local filename = ARGV[2]

-- 1. Get the inode of the file
local inode = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if not inode then
    return -1 -- ENOENT
end

-- 2. Remove it from the parent directory
redis.call('ZREM', 'fs:dir:' .. parent_inode, filename)

-- 3. Decrement nlink
local nlink = redis.call('HINCRBY', 'fs:inode:' .. inode, 'nlink', -1)
if nlink <= 0 then
    -- It's fully detached, clean it up completely
    local content_hash = redis.call('HGET', 'fs:inode:' .. inode, 'content_hash')
    if content_hash then
        redis.call('DEL', 'fs:blob:' .. content_hash)
    end
    redis.call('DEL', 'fs:inode:' .. inode)
    redis.call('DEL', 'fs:dir:' .. inode)
end

return inode
