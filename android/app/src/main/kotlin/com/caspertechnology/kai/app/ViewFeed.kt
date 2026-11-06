package com.caspertechnology.kai.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import com.caspertechnology.kai.link.ServerMsg

/**
 * Kai: puts the parts of each JPEG frame from the computer back together (phone_view.py sends
 * them in pieces so no line of the link nears 64 KiB). Only the newest frame matters: parts
 * of an older one are dropped.
 */
class ViewFeed {
    private var id = -1L
    private var parts = arrayOfNulls<String>(0)

    /** The picture once every part of a frame is in, else null. Runs off the main thread. */
    fun accept(part: ServerMsg.Frame): Pair<Long, Bitmap>? {
        if (part.id != id) {
            if (part.id < id) return null
            id = part.id
            parts = arrayOfNulls(part.parts)
        }
        if (part.part !in parts.indices) return null
        parts[part.part] = part.data
        if (parts.any { it == null }) return null
        val bytes = try {
            Base64.decode(parts.joinToString(""), Base64.DEFAULT)
        } catch (_: IllegalArgumentException) {
            return null
        }
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return null
        return id to bitmap
    }

    fun reset() {
        id = -1L
        parts = arrayOfNulls(0)
    }
}
