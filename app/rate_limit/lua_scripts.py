from __future__ import annotations

SLIDING_WINDOW_SCRIPT = """
local key_prefix = KEYS[1]
local identifier = ARGV[1]
local endpoint = ARGV[2]
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
local now = tonumber(ARGV[5])

local current_wid = math.floor(now / window)
local prev_wid = current_wid - 1

local current_key = key_prefix .. ":" .. identifier .. ":" .. endpoint .. ":" .. current_wid
local prev_key = key_prefix .. ":" .. identifier .. ":" .. endpoint .. ":" .. prev_wid

local prev_count = tonumber(redis.call("GET", prev_key) or "0")

local elapsed_in_window = now - (current_wid * window)
local weight = 1.0 - (elapsed_in_window / window)

local estimated = prev_count * weight

if estimated >= limit then
    local reset_at = (current_wid + 1) * window
    local retry_after = math.ceil(reset_at - now)
    return {0, limit, 0, math.floor(reset_at), retry_after, prev_count, 0}
end

local curr_count = redis.call("INCR", current_key)
if curr_count == 1 then
    redis.call("EXPIRE", current_key, window * 2)
end

local total = estimated + curr_count
if total > limit then
    redis.call("DECR", current_key)
    local reset_at = (current_wid + 1) * window
    local retry_after = math.ceil(reset_at - now)
    return {0, limit, 0, math.floor(reset_at), retry_after, prev_count, curr_count - 1}
end

local remaining = math.max(0, math.floor(limit - total))
local reset_at = (current_wid + 1) * window
return {1, limit, remaining, math.floor(reset_at), 0, prev_count, curr_count}
"""

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local refill_rate = limit / window

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = limit - 1
    last_refill = now
    redis.call("HMSET", key, "tokens", tokens, "last_refill", last_refill)
    redis.call("EXPIRE", key, window * 2)
    local remaining = tokens
    local reset_at = now + window
    return {1, limit, remaining, math.floor(reset_at), 0}
end

local elapsed = now - last_refill
local refill = elapsed * refill_rate
tokens = math.min(limit, tokens + refill)

if tokens < 1 then
    local wait_time = (1 - tokens) / refill_rate
    local reset_at = now + wait_time
    redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
    redis.call("EXPIRE", key, window * 2)
    return {0, limit, 0, math.floor(reset_at), math.ceil(wait_time)}
end

tokens = tokens - 1
redis.call("HMSET", key, "tokens", tokens, "last_refill", now)
redis.call("EXPIRE", key, window * 2)
local remaining = math.floor(tokens)
local reset_at = now + window
return {1, limit, remaining, math.floor(reset_at), 0}
"""

GET_KEY_COUNT_SCRIPT = """
local keys = redis.call("KEYS", ARGV[1])
return #keys
"""
