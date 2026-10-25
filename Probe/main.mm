//
//  main.mm
//  bcmprobe
//
//  Created by laobamac on 2026/9/29.
//  Copyright © 2026 laobamac. All rights reserved.
//

#import <Foundation/Foundation.h>
#import <CoreWLAN/CoreWLAN.h>
#import <IOKit/IOKitLib.h>
#include <sys/sysctl.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        const bool scan = argc == 2 && strcmp(argv[1], "--scan") == 0;
        if (argc > 1 && !scan) {
            fprintf(stderr, "usage: bcmprobe [--scan]\n");
            return 2;
        }
        NSMutableDictionary *report = [NSMutableDictionary dictionary];
        char build[64] = {};
        size_t buildSize = sizeof(build);
        if (sysctlbyname("kern.osversion", build, &buildSize, nullptr, 0) == 0)
            report[@"build"] = @(build);
        io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("SimpleBCM"));
        if (service) {
            CFMutableDictionaryRef properties = nullptr;
            const auto result = IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0);
            if (result == KERN_SUCCESS && properties)
                report[@"SimpleBCM"] = CFBridgingRelease(properties);
            else
                report[@"registryError"] = @(result);
            IOObjectRelease(service);
        } else {
            report[@"SimpleBCM"] = @"not present";
        }
        NSMutableArray *interfaces = [NSMutableArray array];
        for (CWInterface *interface in [CWWiFiClient sharedWiFiClient].interfaces) {
            NSMutableDictionary *info = [NSMutableDictionary dictionary];
            info[@"name"] = interface.interfaceName ?: @"";
            info[@"power"] = @(interface.powerOn);
            info[@"rssi"] = @(interface.rssiValue);
            info[@"noise"] = @(interface.noiseMeasurement);
            info[@"txRate"] = @(interface.transmitRate);
            info[@"mode"] = @(interface.interfaceMode);
            if (scan) {
                NSError *error = nil;
                NSSet<CWNetwork *> *networks = [interface scanForNetworksWithName:nil error:&error];
                if (networks)
                    info[@"scanCount"] = @(networks.count);
                if (error)
                    info[@"scanError"] = @{@"domain": error.domain, @"code": @(error.code)};
            }
            [interfaces addObject:info];
        }
        report[@"interfaces"] = interfaces;
        NSData *data = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:nil];
        if (!data)
            return 1;
        fwrite(data.bytes, 1, data.length, stdout);
        fputc('\n', stdout);
        return 0;
    }
}
