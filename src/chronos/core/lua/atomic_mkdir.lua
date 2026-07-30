-- atomic_mkdir.lua
-- KEYS: []
-- ARGV: [parent_inode, filename, mode, timestamp]

local parent_inode = ARGV[1]
local filename = ARGV[2]
local mode = ARGV[3]
local timestamp = ARGV[4]

-- 1. Check if file already exists in parent directory
local existing_file = redis.call('ZSCORE', 'fs:dir:' .. parent_inode, filename)
if existing_file then
    return -1  -- EEXIST
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

return inode
