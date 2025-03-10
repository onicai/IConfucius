import Result "mo:base/Result";
import Debug "mo:base/Debug";
import Iter "mo:base/Iter";
import Nat8 "mo:base/Nat8";
import Prelude "mo:base/Prelude";
import UUID "mo:uuid/UUID";
import Source "mo:uuid/async/SourceV4";
import Text "mo:base/Text";
import Blob "mo:base/Blob";
import Array "mo:base/Array";
import Random "mo:base/Random";
import Int "mo:base/Int";
import HashMap "mo:base/HashMap";
import Nat32 "mo:base/Nat32";
import Nat "mo:base/Nat";

import Types "Types";

module {
    type Result<Ok, Err> = Result.Result<Ok, Err>;

    /// Returns the value of the result and traps if there isn't any value to return.
    public func get_ok<T, U>(result : Result<T, U>) : T {
        switch result {
            case (#ok value) value;
            case (#err _) Debug.trap("pattern failed");
        };
    };

    /// Returns the value of the result and traps with a custom message if there isn't any value to return.
    public func get_ok_except<T, U>(result : Result<T, U>, expect : Text) : T {
        switch result {
            case (#ok value) value;
            case (#err _) {
                Debug.print("pattern failed");
                Debug.trap(expect);
            };
        };
    };

    /// Unwraps the value of the option.
    public func unwrap<T>(option : ?T) : T {
        switch option {
            case (?value) value;
            case null Prelude.unreachable();
        };
    };

    // Returns the hexadecimal representation of a `Nat8` considered as a `Nat4`.
    func nat4ToText(nat4 : Nat8) : Text {
        Text.fromChar(
            switch nat4 {
                case 0 '0';
                case 1 '1';
                case 2 '2';
                case 3 '3';
                case 4 '4';
                case 5 '5';
                case 6 '6';
                case 7 '7';
                case 8 '8';
                case 9 '9';
                case 10 'a';
                case 11 'b';
                case 12 'c';
                case 13 'd';
                case 14 'e';
                case 15 'f';
                case _ Prelude.unreachable();
            }
        );
    };

    /// Returns the hexadecimal representation of a `Nat8`.
    func nat8ToText(byte : Nat8) : Text {
        let leftNat4 = byte >> 4;
        let rightNat4 = byte & 15;
        nat4ToText(leftNat4) # nat4ToText(rightNat4);
    };

    /// Returns the hexadecimal representation of a byte array.
    public func bytesToText(bytes : [Nat8]) : Text {
        Text.join("", Iter.map<Nat8, Text>(Iter.fromArray(bytes), func(n) { nat8ToText(n) }));
    };

    public func btcTxIdToText(txid : Blob) : Text {
        let reversedArray = Array.reverse<Nat8>(Blob.toArray(txid));
        let txidText = bytesToText(reversedArray);
        return txidText;
    };

    public func newRandomUniqueId() : async Text {
        let g = Source.Source();
        UUID.toText(await g.new());
    };

    // Generalized function to debug print the HashMap
    public func printHashMap<T>(map : HashMap.HashMap<Text, T>, toText : T -> Text) {
        var output : Text = "";
        for ((key, value) in map.entries()) {
            output := output # key # ": " # toText(value) # ", ";
        };
        Debug.print(output);
    };

    public func minNat(a : Nat, b : Nat) : Nat {
        if (a < b) {
            return a;
        } else {
            return b;
        };
    };

    public func nextRandomInt(min : Int, max : Int) : async ?Int {
        if (min > max) {
            //Debug.trap("Min cannot be larger than max");
            return null;
        };
        let range : Nat = Int.abs(max - min) + 1;

        // Calculate the number of bits needed to represent the range
        var bitsNeeded : Nat = 0;
        var temp : Nat = range;
        while (temp > 0) {
            temp := temp / 2;
            bitsNeeded += 1;
        };

        let random = Random.Finite(await Random.blob());
        let ?randVal = random.range(Nat8.fromNat(bitsNeeded)) else return null;
        let randInt = min + (randVal % range);
        ?randInt;
    };

    // Convert a random string to a seed for the LLM model, with wide variability
    public func getRandomLlmSeed(randomString : Text) : Nat32 {
        let value : Nat32 = Text.hash(randomString);

        let selector = value % 6;  // Use last bits to select range between 0-5
        
        switch (selector) {
            case 0 { value % 10 };  // 0-9
            case 1 { value % 100 };  // 0-99
            case 2 { value % 1000 };  // 0-999
            case 3 { value % 1_000_000 };  // 0-999,999
            case 4 { value % 1_000_000_000 };  // 0-999,999,999
            case _ { value };  // Full range
        };
    };

};
