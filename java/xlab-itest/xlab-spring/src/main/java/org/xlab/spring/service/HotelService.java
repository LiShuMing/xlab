/*
 * Copyright 2012-2013 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.xlab.spring.service;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.xlab.spring.domain.City;
import org.xlab.spring.domain.Hotel;
import org.xlab.spring.domain.Review;
import org.xlab.spring.domain.ReviewDetails;


public interface HotelService {

    Hotel getHotel(City city, String name);

    Page<Review> getReviews(Hotel hotel, Pageable pageable);

    Review getReview(Hotel hotel, int index);

    Review addReview(Hotel hotel, ReviewDetails details);

    ReviewsSummary getReviewSummary(Hotel hotel);

}
