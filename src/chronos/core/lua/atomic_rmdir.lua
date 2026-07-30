-- atomic_rmdir.lua
-- KEYS: []
-- ARGV: [parent_inode, filename]

local parent_inode = ARGV[1]
local filename = ARGV[2]

-- 1. Get the inode of the directory
local inode = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if not inode then
    return -1 -- ENOENT
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

return inode
