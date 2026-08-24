/*
 * Copyright 2013 TOYAMA Sumio <jun.nama@gmail.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * ----------------------------------------------------------------------------
 * Derived from the TOYAMA Sumio Unicode Input Helper as maintained by the
 * Appium project (io.appium.settings, UnicodeIME.java), Apache License 2.0.
 *
 * Modifications by the ThumbAgent project (2026):
 *   - Package and class renamed to com.thumbagent.unicodeime.UnicodeImeService.
 *   - Removed all logging of buffered or committed text: input content must
 *     never reach logcat (privacy requirement, see ADR-0019).
 */

package com.thumbagent.unicodeime;

import android.annotation.SuppressLint;
import android.inputmethodservice.InputMethodService;
import android.text.method.MetaKeyKeyListener;
import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CharsetDecoder;

/**
 * Minimal input method that decodes Modified UTF-7 (RFC 3501) text delivered
 * through {@code input text} and commits the decoded Unicode text.
 *
 * <p>The wire text is pure ASCII produced by the host-side encoder
 * ({@code runtime/mobile_agent/domain/unicode_input.py}); this service never
 * receives raw user text over any other channel and exposes no broadcast
 * receivers or IPC endpoints.
 */
public class UnicodeImeService extends InputMethodService {

    @SuppressWarnings("InjectedReferences")
    private static final Charset UTF7_MODIFIED = Charset.forName("x-IMAP-mailbox-name");
    private static final Charset ASCII = Charset.forName("US-ASCII");

    private final CharsetDecoder utf7Decoder = UTF7_MODIFIED.newDecoder();

    /** Shift character that starts a Modified BASE64 block in Modified UTF-7. */
    private static final char M_UTF7_SHIFT = '&';

    /** Character that ends a Modified BASE64 block and shifts back to ASCII. */
    private static final char M_UTF7_UNSHIFT = '-';

    private boolean isShifted = false;
    private long metaState = 0;
    private StringBuilder encodedBlock = new StringBuilder();

    @Override
    public void onStartInput(EditorInfo attribute, boolean restarting) {
        super.onStartInput(attribute, restarting);
        if (!restarting) {
            metaState = 0;
            isShifted = false;
        }
        encodedBlock = new StringBuilder();
    }

    @Override
    public void onFinishInput() {
        super.onFinishInput();
        encodedBlock = new StringBuilder();
    }

    @Override
    public boolean onEvaluateFullscreenMode() {
        return false;
    }

    @SuppressLint("MissingSuperCall")
    @Override
    public boolean onEvaluateInputViewShown() {
        // The helper has no keyboard UI at all.
        return false;
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        int c = getUnicodeChar(keyCode, event);
        if (c == 0) {
            return super.onKeyDown(keyCode, event);
        }

        if (!isShifted) {
            if (c == M_UTF7_SHIFT) {
                shift();
                return true;
            }
            if (isAsciiPrintable(c)) {
                commitChar(c);
                return true;
            }
            return super.onKeyDown(keyCode, event);
        }

        if (c == M_UTF7_UNSHIFT) {
            unshift();
        } else {
            encodedBlock.append((char) c);
        }
        return true;
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        metaState = MetaKeyKeyListener.handleKeyUp(metaState, keyCode, event);
        return super.onKeyUp(keyCode, event);
    }

    private void shift() {
        isShifted = true;
        encodedBlock = new StringBuilder();
        encodedBlock.append(M_UTF7_SHIFT);
    }

    private void unshift() {
        isShifted = false;
        encodedBlock.append(M_UTF7_UNSHIFT);
        String decoded = decodeUtf7(encodedBlock.toString());
        if (getCurrentInputConnection() != null) {
            getCurrentInputConnection().commitText(decoded, 1);
        }
        encodedBlock = new StringBuilder();
    }

    private int getUnicodeChar(int keyCode, KeyEvent event) {
        metaState = MetaKeyKeyListener.handleKeyDown(metaState, keyCode, event);
        int c = event.getUnicodeChar(event.getMetaState());
        metaState = MetaKeyKeyListener.adjustMetaAfterKeypress(metaState);
        return c;
    }

    private void commitChar(int c) {
        if (getCurrentInputConnection() != null) {
            getCurrentInputConnection().commitText(String.valueOf((char) c), 1);
        }
    }

    private String decodeUtf7(String encStr) {
        ByteBuffer encoded = ByteBuffer.wrap(encStr.getBytes(ASCII));
        try {
            CharBuffer buf = utf7Decoder.decode(encoded);
            return buf.toString();
        } catch (CharacterCodingException e) {
            // Undecodable input is committed as-is; the host-side read-back
            // verification (TEXT_INPUT_NOT_VERIFIED) catches the mismatch.
            return encStr;
        }
    }

    private static boolean isAsciiPrintable(int c) {
        return c >= 0x20 && c <= 0x7E;
    }
}
