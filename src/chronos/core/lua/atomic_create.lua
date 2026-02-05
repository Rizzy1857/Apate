-- atomic_create.lua
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
local inode_counter = redis.call('INCR', 'fs:next_inode')

-- 3. Create inode metadata
-- Default umask logic or passed mode should handle permissions
-- uid/gid 0 (root) by default
redis.call('HSET', 'fs:inode:' .. inode_counter,
    'mode', mode,
    'uid', 0,
    'gid', 0,
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

return inode_counter
